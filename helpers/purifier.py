import click
import requests
import cc.settings_sync

M_DECLINE_DEVICE_APPROVAL = '''mutation DeclineDevice($device_id: String!, $public_device_key: String!)
{
    declineDevice(device_id: $device_id, public_device_key: $public_device_key)
}
'''

M_REMOVE_USER_SHARE = '''mutation DeleteShare($storage_type: String!, $unique_id: String!)
{
    deleteShare(storage_type: $storage_type, unique_id: $unique_id)
}'''

M_RESET_USER_KEYS = '''mutation ResetUserKeys($id: String!)
{
    resetUserKeys(id: $id){id public_key}
}'''

Q_USER_INFORMATION = '''{
  currentUser
  {
    id
    email
    approval_requests { device_id public_device_key }
    csps { shares { unique_id storage_type } } } }'''

def ac_request(session, query, variables = {}):
    response = session.post(cc.settings_sync.GRAPHQL_URL, json={'query': query,
                                                                'variables': variables})
    click.secho("AC Response: '{}'".format(response.content))
    response.raise_for_status()
    return response


def remove_user_keys(session, current_user):
    """Remove user keys from admin console."""
    if click.confirm("Purging keys for user '{}'?".format(current_user['email']), default=False):
        return ac_request(session, M_RESET_USER_KEYS, {'id': current_user['id']})


def remove_user_shares(session, current_user):
    click.secho("Shares for user '{}'.".format(current_user['email']))
    for storage_provider in current_user['csps']:
        for share in storage_provider['shares']:
            if click.confirm("Remove share '{}'?".format(share), default=True):
                ac_request(session, M_REMOVE_USER_SHARE, share)

def decline_device_approvals(session, current_user):
    click.secho("Device Approvals for user '{}'.".format(current_user['email']))

    for device_approval in current_user['approval_requests']:
        if click.confirm("Decline approval for '{}'?".format(device_approval['device_id']), default=True):
            print(device_approval)
            ac_request(session, M_DECLINE_DEVICE_APPROVAL, device_approval)

@click.command()
@click.option('--username', prompt=True, hide_input=False)
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=False)
def wipe(username, password):
    click.secho("Trying to login as '{}'".format(username))
    session = requests.session()
    session.headers['X-Api-Version-Expected'] = cc.settings_sync.EXEPECETD_API_VERSION
    res = session.post(cc.settings_sync.TOKEN_URL, json={'email': username, 'password': password})
    assert res.status_code == 200
    token = res.json()
    session.headers = {'Authorization': 'Bearer {}'.format(token['token'])}
    click.secho("Obtained token '{}'".format(token['token']))

    resp = session.post(cc.settings_sync.GRAPHQL_URL, json={'query': Q_USER_INFORMATION})
    resp.raise_for_status()
    current_user = resp.json()['data']['currentUser']
    click.secho("Authentication Data: {}".format(current_user))

    decline_device_approvals(session,current_user)
    remove_user_keys(session, current_user)
    remove_user_shares(session, current_user)


if __name__ == '__main__':
    click.echo("AdminConsole: {}".format(cc.settings_sync.HOST))
    click.echo("GraphQL URL: {}".format(cc.settings_sync.GRAPHQL_URL))
    click.echo("Token URL: {}".format(cc.settings_sync.TOKEN_URL))
    wipe()


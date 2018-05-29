"""Utillity Script for Administrators."""
import os
import shutil

import click
from cc import config
import cc.crypto2


@click.group()
def admin():
    """Admin command group."""
    pass


@admin.command()
@click.option('--private-key', help='The path to the master key pem.', required=True,
              type=click.Path(exists=True))
@click.option('--target-directory', help='The target of the decrypted files', default='decrypted')
@click.argument('file', type=click.Path(exists=True))
def decrypt_files(private_key, target_directory, file):
    """Decrypt the specified file with the master key."""

    def get_key(subject):
        """Return passed master key if subject starts with master."""
        if subject.startswith('master'):
            return open(private_key, 'rb').read()
        else:
            raise KeyError

    os.makedirs(target_directory, exist_ok=True)

    with open(os.path.join(target_directory, file), 'wb') as file_out, \
            open(file, 'rb') as file_in:
        file_in_wrapped = cc.crypto2.DecryptionFileWrapper(file_in, get_key)
        shutil.copyfileobj(file_in_wrapped, file_out)


@click.group()
def config_rename():
    """Config command group."""
    pass


@config.command()
@click.argument('file', required=False, type=click.Path())
def dump_config(file):
    """Dump local configuration using the configuration key/tag stored in the system keychain.

    If no file is given it will try to read the current configuration file from the known location.
    """
    # pylint: disable=protected-access,redefined-outer-name
    try:
        if not file:
            file = config.config_file
            click.echo(click.style("No file given. Using default at '{}'".format(file),
                                   fg='yellow'),
                       err=True)

        key = config.get_configuration_key(auto_create=False)
        tag = config.get_configuration_tag()
        config = config._read_encrypted_configuration(file, key, tag)
        click.echo_via_pager(config)
    except config.ConfigurationError as exception:
        click.echo(click.style(exception, fg='red'), err=True)
    except FileNotFoundError:
        click.echo(click.style("No configuration file found at '{}'!".format(file), fg='red'),
                   err=True)


if __name__ == '__main__':
    click.CommandCollection(sources=[config, admin])()

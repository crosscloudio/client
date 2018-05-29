# Build Configurations

To deliver different builds to different clients there is a build config for each costumer. It uses the metadata label from semver to mark the version. E.g. `1.0.1-uni-salzburg` tries to copy the `build-config/uni-salzburg.json` file to same directory as the cx_freeze executable (`crosscloud.exe` on windows).

Fields:

- `admin_console.url`: The url to reach the admin console.
- `admin_console.fingerprint`: The sha-256 fingerprint of the admin-console certificate. You can obtain that in the certificate viewer in Chrome (just strip all the whitespaces). 

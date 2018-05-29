# Developer mode

Instructions to run the client in developer mode and be able to test code changes

## Prerequisites

* Python (3.5.3)
* nodejs (v6.9.2 LTS)
* [Yarn](https://yarnpkg.com/en/docs/install) (version 0.18 or higher)
* virtualenv:
- This needs to be created with ```python3 -m venv .venv```
- Pay attention to that the venv needs to be at ```client/Core/.venv``` not in 
client directly. The name matters here. 

# Steps
 
1. Run the virtualenv in ```client/Core```
2. Run ```pip install -r ..\Core\requirements.txt```
3. Move to ```client\electron-ui```
4. Run ```yarn install```
5. Run ```set PYTHONPATH=..\Core``` (Windows), ```export PYTHONPATH=../Core``` (Unix)
6. Run ```node_modules\.bin\webpack --progress -c -d ```
7. Run ```node_modules\.bin\electron .```

# Environment Variables
The electron-ui will react to the following environmental variables: 
- CC_DEVTOOLS to any value: opens the chrome developer tools upon start
- CC_UPDATE_POLL_TIME to number: ms of update intervall: per default, the updater 
checks for updates every 4hours starting from the application start. 
If this variable is set, the update intervall can be set to the value in ms (!!).
- CC_ADMIN_CONSOLE_URL: Set the fallback admin console URL if not specified in build config.

## Debugging

The following set of variables can be used to influence the clients logging behaviour and setup.

- Set `CC_DEBUG` to enable `debug` level output for (almost all) internal `cc` modules in `production`.
- Point `CC_LOGGING_CFG` to a `logging` compatible `.json` based configuration to set your own logging handlers, formats etc.
  This is only possible in `development`!

# GUI code style 
[Eslint](http://eslint.org/) is used for linting JavaScript source code.
The project uses slightly modified
[Airbnb's preset for eslint](https://github.com/airbnb/javascript).
Linter can be run locally with the following command:
```bash
npm run lint
```

# installing the pre-commit hook
## on linux and macos
```
ln -s `pwd`/git-commit-hooks/pre-commit.py .git/hooks/pre-commit
```

## on windows
copy it and change the shebang as in the comment



# How to do a release

Tag it with `vX.X.X-<target>` where target is something with a build-config (e.g. `demo`). Build the explorer extension and the the electron mac and electron windows part. To upload the release to the update server note the build_number from the gitlab url. Then go to `helpers/upload-release` create a venv and install the things from `requirmenets.txt`.

Now add the key from the update server (atm the one from digital-ocean) to your ssh agent.

Then a 
```
fab upload_release:build_number=<>
```

will upload everything to the correct path on the server side. Afterwards it will be available on the corresponding admin-console page and via update.
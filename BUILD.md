Here are the details related to building the client with Windows.

# Prerequisites

* **Python v3.4.4**
* GitLab ssh key
* Recommended to use virtualenv for the procces
* nodejs
* wixtools

## virtualenv

* Run **virtualenv _path_** to create the folder where it's gonna be located.
* Run the *activate* script under the _Scripts_ folder.
* Run the *deactivate* script to stop using virtualenv.

## wixtools
* Remember to add the _/bin_ folder inside the directory to the %path.

# Core
* Go to the _core_ folder.
* On the command line run ```pip install -r requirements.txt``` to install al the packages needed.
    - In case you have trouble with the Windows cmd, try it in the Git Bash, you might need to activate.
    the Windows cmd in there by typing ```cmd``` first.
* During this process you will be asked for the password of your encryption key while trying to download some dependencies.
* Once it has finished, do the build with ```python file.py build```. In this case the target will be _setup.py_.

# Electron-ui
* Go to the _electron-ui_ folder.
* Copy the files inside _client\Core\build\exe.win32-3.4_ to the _client\electron-ui\daemon\prod_ folder.
* Run ```npm install -g gulp-cli```.
* Run ```npm install```.
* Run ```gulp build```.

# Build the msi
* Go to the msi-setup folder.
* Import _win32api_ module ```pip install pypiwin32```.
* Run ```python generate_bundle electronPath version build```.
    - _electronPath_ is ../electron-ui/build/dist/win-ia32-unpacked.
    - _version_ has the following format X.X.X WHERE X is a number.
* Run ```candle crosscloud.wxs```.
* Run ```light crosscloud.wixobj```.
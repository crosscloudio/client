# General
TODO

# Run
TODO

# Build

```
npm install -g gulp-cli
yarn install
gulp build
```

# Environment Variables
The electron-ui will react to the following environmental variables: 
- CC_DEVTOOLS -> any value: opens the chrome developer tools upon start
- CC_UPDATE_POLL_TIME -> ms of update interval: per default, the updater 
checks for updates every 4hours starting from the application start. 
If this variable is set, the update interval can be set to the value in ms (!!). 

# Code style
[Prettier](https://prettier.io) is used for automatic code formatting.
To format the code run the following command:

```bash
npm run prettier
```


[Eslint](http://eslint.org/) is used for linting JavaScript source code.
The project uses slightly modified
[Airbnb's preset for eslint](https://github.com/airbnb/javascript).

Linter can be run locally with the following command:

```bash
npm run eslint
```

# Assets
When adding svg assets, make sure to clean it from editor metadata by running: 
```
npm install -g svgo
svgo -f ../path/to/folder/with/svg/files
```

# upload script

This is a script to upload a release to our update server. 
Just create a virtualenv with py3 and install the deps from `requirements.txt` and start it with
```
venv/bin/fab upload_release:build_number=<the build number>
```

you have to start it for mac and windows seperatly.

# Regenerate virtualenv

Sometimes we have to regenerate the contents of `venv` folder. It can be done with the following steps:

```bash
rm -rf venv
python3.XXX -m venv venv
script/setup
deactivate
. venv/bin/activate
```

Where `XXX` is the required python version.

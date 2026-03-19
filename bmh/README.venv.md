# Regenerate virtualenv

Sometimes we have to regenerate the contents of `venv` folder. It can be done with the following steps:

```bash
rm -rf venv
python3.XXX -m venv venv
. venv/bin/activate
script/setup
```

Where `XXX` is the required python version.

# Install requirements

Under Raspberry Pi `script/setup` can fail. Unfortunately `uv` starts multiple `python` commands parallelly even if we set concurrency related environment variables. A weaker RPi can run out of memory and reboot in such cases. It is possible to circumvent it by forcing sequential installation of requirements:

```bash
cat requirements_test_all.txt | grep -v "#" | grep -ve "^$" | while read PACK; do
        echo $PACK
        uv pip install --upgrade $PACK
done

script/setup
```

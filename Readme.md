# Stripe DATEV Exporter


## Environment
If you don't have, install pipenv:

```
apt install pipenv
python3 -m pip install pipenv
```

Install dependancs with pipenv:

```
pipenv install requests
```

Uses Python's virtualenv. To setup initially:

```
virtualenv -p python3 venv
```

Add STRIPE_API_KEY to venv.bin.activate like: 

```
export STRIPE_API_KEY="rk_live_..."
```
and
```
deactivate () {
    ...
    # Unset variables
        unset STRIPE_API_KEY 
}
```

To activate in your current shell:

```
. venv/bin/activate
```

Run app with year and month:

```
python3 stripe-datev-cli.py 2021 06
```
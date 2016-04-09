## AnkiStats

This is a Python application that extracts a limited set of statistics from an Anki collection and uploads them to a web server. This is the local client side of this system. If you are interested in the server side, you should check out the companion project [AnkiStatsServer](https://github.com/NSBum/AnkiStatsServer).

### Installation instructions

#### Assumptions

- You should a working Python 2.7 distribution on your local machine.
- You should have a target collection whose statistics you wish to collect.

#### Clone the repo

``` bash
$ git clone https://github.com/NSBum/AnkiStatsServer.git
```

#### Edit configuration details

You will want to supply your own configuration details in `mystats.ini`.

``` ini
[Collection]
Path: /Users/alan/Documents/Anki/Alan - Russian/collection.anki2

[Server]
url: http://127.0.0.1
port: 5000
uploadPath: /data
```

### Run the application

``` bash
$ python mystats.py
```

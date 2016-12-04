#!/usr/bin/env python

import sqlite3
import json
import urllib2
import ConfigParser

import anki.storage
import anki.stats

#   load our configuration
config = ConfigParser.ConfigParser()
config.read('mystats.ini')

def configSectionMap(section):
    configMap = {}
    options = config.options(section)
    for option in options:
        try:
            configMap[option] = config.get(section,option)
        except:
            configMap[option] = None
    return configMap
print

# path to the sqlite collection file
collection_path = configSectionMap('Collection')['path']

# initialize a collection object for this collection
# and obtain the statistics
ankicollection = anki.storage.Collection(collection_path)
stats = anki.stats.CollectionStats(ankicollection)

# whole collection or a single deck?
if int(configSectionMap('Stats')['all']) == 1:
    stats.wholeCollection = True
else:
    stats.wholeCollection = False
    deckname = configSectionMap('Stats')['deck']
    deck_id = stats._didForDeckName(deckname)
    print 'Deck id = {0}'.format(deck_id)
    if deck_id == -1:
        print "ERROR: no deck with configured name"
        raise ValueError('There is no deck with the configured name')

# configure url for data upload
url = configSectionMap('Server')['url'] + ':'
url += configSectionMap('Server')['port']
url += configSectionMap('Server')['uploadpath']

#stats._didForDeckName("Every card")

req = urllib2.Request(url)
req.add_header('Content-Type', 'application/json')
json_data = json.dumps(stats.todayStats_(), cls=anki.stats.StatsEncoder)
print json_data

try:
    response = urllib2.urlopen(req, json_data )
except urllib2.HTTPError as e:
    if e.code == 404:
        print 'Unknown path'
    else:
        print 'Unknown error: {}'.format(e.code)
except urllib2.URLError as e:
    print 'Error - not HTTP specific'
else:
    body = response.read()
    print body

# -*- coding: utf-8 -*-

# Portions of this code are:
# Copyright: Damien Elmes <anki@ichi2.net>
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
# Including the True Retention add-on https://ankiweb.net/shared/info/613684242

from __future__ import division
import time
import datetime
import json
import pprint

#import anki.js
from anki.utils import fmtTimeSpan, ids2str
from anki.lang import _, ngettext

# Collection stats
##########################################################################

colYoung = "#7c7"
colMature = "#070"
colCum = "rgba(0,0,0,0.9)"
colLearn = "#00F"
colRelearn = "#c00"
colCram = "#ff0"
colIvl = "#077"
colHour = "#ccc"
colTime = "#770"
colUnseen = "#000"
colSusp = "#ff0"

pp = pprint.PrettyPrinter(indent=4)

# Object for daily statistics
class DayStats_(object):
    def __init__(self):
        self.total = 0
        self.learn = 0
        self.review = 0
        self.relearn = 0
        self.filter = 0
        self.duration = 0
        self.mcnt = 0
        self.msum = 0
        self.time = None

        #   cards due tomorrow
        self.tomorrow = 0

        #   number of notes tagged as vocabulary
        self.vocab = 0

        #   today number of cards in the collection
        self.tcount = 0

# JSON Encoder for DayStats_
class StatsEncoder(json.JSONEncoder):
    def default(self, obj):
        if not isinstance(obj, DayStats_):
            return super(StatsEncoder, self).default(obj)
        return obj.__dict__

class CollectionStats(object):
    def __init__(self, col):
        self.col = col
        self._stats = None
        self.type = 0
        self.width = 600
        self.height = 200
        self.wholeCollection = False

    def todayStats_(self):
        lim = self._revlogLimit()
        if lim:
            lim = " and " + lim
        cards, thetime, failed, lrn, rev, relrn, filt = self.col.db.first("""
select count(), sum(time)/1000,
sum(case when ease = 1 then 1 else 0 end), /* failed */
sum(case when type = 0 then 1 else 0 end), /* learning */
sum(case when type = 1 then 1 else 0 end), /* review */
sum(case when type = 2 then 1 else 0 end), /* relearn */
sum(case when type = 3 then 1 else 0 end) /* filter */
from revlog where id > ? """+lim, (self.col.sched.dayCutoff-86400)*1000)
        cards = cards or 0
        thetime = thetime or 0
        failed = failed or 0
        lrn = lrn or 0
        rev = rev or 0
        relrn = relrn or 0
        filt = filt or 0

        _todayStats = DayStats_()
        _todayStats.time = self.col.sched.dayCutoff-86400
        _todayStats.total = cards
        _todayStats.review = rev
        _todayStats.relearn = relrn
        _todayStats.learn = lrn
        _todayStats.filter = filt
        _todayStats.duration = thetime
        _todayStats.trueRetention = self.trueRetentionDay()
        (low, avg, high) = self._easeFactors()
        _todayStats.lowEase = low
        _todayStats.avgEase = avg
        _todayStats.highEase = high

        mcnt, msum = self.col.db.first("""
select count(), sum(case when ease = 1 then 0 else 1 end) from revlog
where lastIvl >= 21 and id > ?"""+lim, (self.col.sched.dayCutoff-86400)*1000)

        _todayStats.mcnt = mcnt
        _todayStats.msum = msum

        tomorrow = self.col.db.scalar("""
select count() from cards where did in %s and queue in (2,3)
and due = ?""" % self._limit(), self.col.sched.today+1)
        _todayStats.tomorrow = tomorrow

        #   how many notes are tagged with vocabulary tags
        vocab = self.col.db.scalar("""
SELECT COUNT(*) from notes WHERE tags LIKE '%category::vocabulary%'"""
        )
        _todayStats.vocab = vocab

        #   total card count
        tcount = self.col.db.scalar("""
SELECT COUNT(*) from cards
        """)
        _todayStats.tcount = tcount

        #   numbers of card types
        _todayStats.mtr, _todayStats.yng, _todayStats.new, _todayStats.susp = self._cards()

        #   collect data on the percent good for each of the card
        #   types learning, young and mature
        #   these are fractions 0 - 1.0 rounded to 3 decimals
        easePercents = self.easeData()
        _todayStats.good_lrn = easePercents[0]
        _todayStats.good_yng = easePercents[1]
        _todayStats.good_mature = easePercents[2]

        return _todayStats

    #   compute the true retention rate for a given span, day limit
    def trueRetention(self, lim, span):
        flunked, passed, learned, relearned = self.col.db.first("""
        select
        sum(case when ease = 1 and type == 1 then 1 else 0 end), /* flunked */
        sum(case when ease > 1 and type == 1 then 1 else 0 end), /* passed */
        sum(case when ivl > 0 and type == 0 then 1 else 0 end), /* learned */
        sum(case when ivl > 0 and type == 2 then 1 else 0 end) /* relearned */
        from revlog where id > ? """+lim, span)
        flunked = flunked or 0
        passed = passed or 0
        learned = learned or 0
        relearned = relearned or 0
        try:
            temp = "%0.3f" %(passed/float(passed+flunked))
        except ZeroDivisionError:
            temp = "N/A"
        return temp

    def _cards(self):
        return self.col.db.first("""
    select
    sum(case when queue=2 and ivl >= 21 then 1 else 0 end), -- mtr
    sum(case when queue in (1,3) or (queue=2 and ivl < 21) then 1 else 0 end), -- yng/lrn
    sum(case when queue=0 then 1 else 0 end), -- new
    sum(case when queue<0 then 1 else 0 end) -- susp
    from cards where did in %s""" % self._limit())

    def trueRetentionDay(self):
        lim = self._revlogLimit()
        if lim:
            lim = " and " + lim
        return self.trueRetention(lim, (self.col.sched.dayCutoff-86400)*1000)

    def easeData(self):
        d = {'lrn':[], 'yng':[], 'mtr':[]}
        types = ("lrn", "yng", "mtr")
        eases = self._eases()
        for (type, ease, cnt) in eases:
            if type == 1:
                ease += 5
            elif type == 2:
                ease += 10
            n = types[type]
            d[n].append((ease, cnt))
            #return d
            return self._easeInfo(eases)

    def _eases(self):
        lims = []
        lim = self._revlogLimit()
        if lim:
            lims.append(lim)
        if self.type == 0:
            days = 30
        elif self.type == 1:
            days = 365
        else:
            days = None
        if days is not None:
            lims.append("id > %d" % (
                (self.col.sched.dayCutoff-(days*86400))*1000))
        if lims:
            lim = "where " + " and ".join(lims)
        else:
            lim = ""
        return self.col.db.all("""
select (case
when type in (0,2) then 0
when lastIvl < 21 then 1
else 2 end) as thetype,
(case when type in (0,2) and ease = 4 then 3 else ease end), count() from revlog %s
group by thetype, ease
order by thetype, ease""" % lim)

    def _easeInfo(self, eases):
        types = {0: [0, 0], 1: [0, 0], 2: [0,0]}
        for (type, ease, cnt) in eases:
            if ease == 1:
                types[type][0] += cnt
            else:
                types[type][1] += cnt
        i = []
        for type in range(3):
            (bad, good) = types[type]
            tot = bad + good
            try:
                pct = round(good / float(tot),3)
            except:
                pct = 0
            i.append(pct)
        return i

    def _easeFactors(self):
        return self.col.db.first("""
        select
        min(factor) / 10.0,
        avg(factor) / 10.0,
        max(factor) / 10.0
        from cards where did in %s and queue = 2""" % self._limit())

    def _limit(self):
        if self.wholeCollection:
            return ids2str([d['id'] for d in self.col.decks.all()])
        return self.col.sched._deckLimit()

    def _revlogLimit(self):
        if self.wholeCollection:
            return ""
        return ("cid in (select id from cards where did in %s)" %
                ids2str(self.col.decks.active()))

    def _didForDeckName(self,name):
        pp = pprint.PrettyPrinter(indent=4)
        did = -1
        deck_json_data = self.col.decks.decks
        for attribute, value in deck_json_data.iteritems():
            did = int(attribute)
            found_name = deck_json_data[attribute]["name"]
            pp.pprint(name)
            if found_name == name:
                break
        return did

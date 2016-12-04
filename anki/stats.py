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

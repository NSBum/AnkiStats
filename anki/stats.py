# -*- coding: utf-8 -*-
# Copyright: Damien Elmes <anki@ichi2.net>
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import division
import time
import datetime
import json

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

        return _todayStats

    def _limit(self):
        if self.wholeCollection:
            return ids2str([d['id'] for d in self.col.decks.all()])
        return self.col.sched._deckLimit()

    def _revlogLimit(self):
        if self.wholeCollection:
            return ""
        return ("cid in (select id from cards where did in %s)" %
                ids2str(self.col.decks.active()))

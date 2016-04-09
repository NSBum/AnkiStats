## AnkiStats

The AnkiStats project offers a means of tracking your [Anki]() statistics. [Anki]() is a spaced-repetition software package that is frequently used to memorize large amounts of information, often foreign language vocabulary. As the user completes a block of memorization work, Anki generates statistics on his performance. These statistics are useful for tracking progress and learning efficiency over time.

While Anki generates a graph of the statistics, it does not save them in a way that makes tracking _outside of Anki_ possible. Thus, AnkiStats.

AnkiStats simply asks for a subset of the statistics and uploads them to a web server running an API that captures the statistics and saves them to a MySQL database. What you do with the stats from there is up to you.

# Fetching data from Mail Archives

Many software development projects use mailing lists as a mean for coordination. Mailing
lists can be archived in many different ways, but maybe the most classical is using the
mbox format. This format is simple: messages are stored in a file with the beginning of
each one indicated by a line starting with the string “From ”. Perceval has a backend for
supporting `mbox` archives, with the imaginative name mbox. Unfortunately, there are several
variations of the basic format: Perceval does its best for parsing all those variations.

### Parsing mbox archives

As in other cases, we can start by asking Perceval for some help:

```
(perceval) $ perceval mbox --help
```

From the banner it produces, we learn that the most simple usage is specifying the uri for
the mailing list to analyze, and a directory with its archives. The uri is used for
annotation purposes, and can really be any string (although it should usually be a link to
the mailing list webpage). The directory needs to be filled with files, each of them in
mbox format. So, let’s start by getting one archive:

```
(perceval) $ mkdir archives
(perceval) $ wget -P archives http://mail-archives.apache.org/mod_mbox/httpd-announce/201607.mbox
```

These two lines (assuming we already have wget installed), will retrieve the archive
corresponding to July 2016 of the mailing list `httpd-announce`, of the Apache project.
The option `-P archives` to wget will ensure that the file is stored in the `archives`
directory, which we created in the previous line.

Once we have the archive, we can analyze it:

```bash
(perceval) $ perceval mbox httpd-announce archives > perceval.log
[2016-11-23 02:12:02,476] - Sir Perceval is on his quest.
[2016-11-23 02:12:02,477] - Looking for messages from 'httpd-announce' on 'archives' since 1970-01-01 00:00:00+00:00
[2016-11-23 02:12:02,488] - Done. 4/4 messages fetched; 0 ignored
[2016-11-23 02:12:02,488] - Fetch process completed
[2016-11-23 02:12:02,488] - Sir Perceval completed his quest.
```

The above message show how the `archives` directory was parsed looking for mbox files, how 4
messages were found, of which none was ignored. Since the output was redirected to
`perceval.log`, now we have the JSON documents produced by Perceval in that file:

```
{
    "backend_name": "MBox",
    "backend_version": "0.6.0",
    "category": "message",
    "data": {
        "Authentication-Results": "spamd4-us-west.apache.org (amavisd-new);\n\tdkim=pass (2048-bit key) header.d=comcast.net",
        "Content-Transfer-Encoding": "7bit",
        "Content-Type": "text/plain; charset=us-ascii",
        "DKIM-Signature": "v=1; a=rsa-sha256; c=relaxed/relaxed; d=comcast.net;\n\ts=q20140121; t=1467724082;\n\tbh=+4noOLzzrCDUMpdmYJUqt/JMcTXlHPAr2vhKyFryBUY=;\n\th=Received:Received:From:Content-Type:Subject:Message-Id:Date:To:\n\t Mime-Version;\n\tb=jlfQ9jFzyv9EP/ioD4B3TgJF7U3S60MygklSXCmpSftTp78gxYY502XgMsV5WAYaK\n\t t9a2O7Hssmbfi5U+rZ8R0hhtFqDyfsbE6xxUvfHvSyHAjJ7XISwxQnvEJ/EhLeN3G7\n\t Ht/mIz9uim8atrnxSaZDyO09t5JoM70aPFBmbTSE9+3bWJDi8M/Apvsj/q+Zu1jHJ1\n\t buxk9iitgmFegKUfSktydc6tFE4y8yObF41n4EAHC2uuURPbtXwWHWRH/nap4sK/aI\n\t FwIMTEbbNyEC0/wEqy0dktUYX2pnakh8DdH+TX34ozKKr9exGAFYwgoGQEvnPAhRJi\n\t FdxJf5QfRfMeg==",
        "Date": "Tue, 5 Jul 2016 09:08:01 -0400",
        "Delivered-To": "moderator for announce@httpd.apache.org",
        "From": "Jim Jagielski <jim@apache.org>",
        "List-Id": "<announce.httpd.apache.org>",
        "List-Post": "<mailto:announce@httpd.apache.org>",
        "Mailing-List": "contact announce-help@httpd.apache.org; run by ezmlm",
        ...
        "body": {
            "plain": "\n          Apache HTTP Server 2.4.23 Released\n\nThe Apache Software Foundation and the Apache HTTP Server Project\nare pleased to announce the release of version 2.4.23 of the Apache\nHTTP Server (\"Apache\"). 
            ...
...
```

We can see the usual structure of a Perceval JSON document, with some metainformation
(such as `backend_name`), and all the content the corresponding message in the `data`
field. The structure of that content is one field per header, with the same name the
header has in the message. For the body of the message, the field `body` is used.


If we have several mbox files in the directory, all of them will be analyzed at once. For
example, we can add a new archive to the `archives` directory above, and run Perceval
again:

```bash
(perceval) $ wget -P archives http://mail-archives.apache.org/mod_mbox/httpd-announce/201608.mbox
(perceval) $ perceval mbox httpd-announce archives > perceval.log
[2016-11-23 11:12:37,795] - Sir Perceval is on his quest.
[2016-11-23 11:12:37,797] - Looking for messages from 'httpd-announce' on 'archives' since 1970-01-01 00:00:00+00:00
[2016-11-23 11:12:37,814] - Done. 5/5 messages fetched; 0 ignored
[2016-11-23 11:12:37,814] - Fetch process completed
[2016-11-23 11:12:37,814] - Sir Perceval completed his quest.
```

Now, 5 messages were analyzed, since the new archive (for August 2016) contains just one,
and we already had 4 in the first archive we downloaded (for July 2016).

In this case, we can also see a small difference on the body of the messages. For the last one we obtain in perceval.log, we can see how the `body` field is a dictionary with a field named `html`. That’s because the content is labeled in the original message as being in HTML format. Compare this to the first example above, where the `body` field contains a field named plain, because the content is in plan (unformatted) format.

```
"body": {
            "html": "<head >\n<STYLE>\n .headerTop { background-color:#FFCC66;
```

### Analyzing messages with Python

As usual, we can use Perceval as a Python module for analyzing messages in mbox files.
Using the same two `archives` we downloaded above, in the archives directory, we can for
example show the subject for all messages (code below is in `perceval_mbox_1.py`]:

```py
#! /usr/bin/env python3

from perceval.backends.core.mbox import MBox

# uri (label) for the mailing list to analyze
mbox_uri = 'http://mail-archives.apache.org/mod_mbox/httpd-announce/'
# directory for letting Perceval where mbox archives are
# you need to have the archives to analyzed there before running the script
mbox_dir = 'archives'

# create a mbox object, using mbox_uri as label, mbox_dir as directory to scan
repo = MBox(uri=mbox_uri, dirpath=mbox_dir)
# fetch all messages as an iteratoir, and iterate it printing each subject
for message in repo.fetch():
    print(message['data']['Subject'])
```

To run the script, just move to the parent of the `archives` directory, that has our mbox
archives, and run:

```bash
(perceval) $ python3 perceval_mbox_1.py 
[ANNOUNCE] Apache HTTP Server 2.4.23 Released
CVE-2016-4979: HTTPD webserver - X509 Client certificate ba
PC Prfoessional per Scuole e Enti Pubblici da 90 Euro
Web Designing Services at Lowest Prices!!
Vai in vacanza con l'iPhone e le Beats
```

Which shows us how some spam got into the Apache `httpd-announce` mailing list, by the way.

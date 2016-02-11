# Analyzing a GitHub repository

As a proof of concept of how Perceval works, it can be used to retrieve data from a certain GitHub repository (git and issues), upload it to ElasticSearch, and produce a Kibana-based dashboard with it.

To make this procedure easy and repetable, despite changes in Perceval (which may be still be frequent), we have used a specific version of Perceval (tagged "fosdem16"), and some scripts (found in [GrimoireELK](http://github.com/grimoirelab/GrimoireELK), which upload data to ElasticSearch and produce the dashboard automatically.

The procedure is described in the [slides for a talk at FOSDEM 2016](https://speakerdeck.com/jgbarah/learning-about-software-development-with-kibana-dashboards), and summarized below.

Create and activate virtualenv for Python

```
$ virtualenv -p /usr/bin/python3 gitlab
$ source gitlab/bin/activate
```

Install dependencies

```
(gitlab) $ pip install beautifulsoup4
(gitlab) $ pip install python-dateutil
(gitlab) $ pip install requests
(gitlab) $ pip install six
```

Install perceval, from GrimoireLab git repo

```
(gitlab) $ git clone https://github.com/grimoirelab/perceval.git
(gitlab) $ cd perceval
(gitlab) $ python3 setup.py install
(gitlab) $ cd ..
```

Clone GrimoireELK GrimoireLab git repo, checkout branch fosdem16

```
(gitlab) $ git clone https://github.com/grimoirelab/GrimoireELK.git
(gitlab) $ cd GrimoireELK
(gitlab) $ git checkout fosdem16
(gitlab) $ cd ..
```

Clone the MetricsGrimoire/Bicho repository, and run git log. Then analyze it

```
(gitlab) $ git clone https://github.com/MetricsGrimoire/Bicho
(gitlab) $ cd Bicho
(gitlab) $ git log --raw --numstat --pretty=fuller --decorate=full --parents -M -C -c --remotes=origin --all > /tmp/bicho-gitlog.log
(gitlab) $ cd ../GrimoireELK/util
(gitlab) $ python3 ./p2o.py -e http://localhost:9200 --no_inc --debug git /tmp/bicho-gitlog.log
(gitlab) $ python3 ./p2o.py -e http://localhost:9200 --no_inc --debug --enrich_only git /tmp/bicho-gitlog.log
 ...
2016-01-31 00:47:26,960 Deleted and created index http://localhost:9200/git__tmp_bicho-gitlog.log_enrich
 ...
```

Retrieve GitHub issues for MetricsGrimoire/Bicho. Instead of http://localhost:9200, use the url for your Elasticsearch server. Use your GitHub token (obtained from GitHub) instead of XXX.

```
(gitlab) $ python3 ./p2o.py -e http://localhost:9200 --no_inc --debug github --owner metricsgrimoire --repository bicho --token XXXX
(gitlab) $ python3 ./p2o.py -e http://localhost:9200 --no_inc --debug --enrich_only github --owner metricsgrimoire --repository bicho --token XXXX
 ...
2016-01-31 00:45:37,269 Deleted and created index http://localhost:9200/github_https:__github.com_metricsgrimoire_bicho_enrich
 ...
```

Create dashboards from templates. First, upload templates to ElasticSearch.

```
(gitlab) $ python3 ./kidash.py -e http://localhost:9200 -g --import ../dashboards/git-activity.json
(gitlab) $ python3 ./kidash.py -e http://localhost:9200 -g --import ../dashboards/github-pr-bubbles-geoMap.json
```

Now, produce the actual dashboards, by running e2k.py on the templates, specifying the indexes. Use the index names that you saw above, when running p2o.py.

```
(gitlab) $ python3 ./e2k.py -g -e http://localhost:9200 -d "Git-Activity" -i git__tmp_bicho-gitlog.log_enrich
(gitlab) $ python3 ./e2k.py -g -e http://localhost:9200 -d "PRBubblesGeoMap" -i github_https:__github.com_metricsgrimoire_bicho_enrich
```

## Installing ElasticSearch, Kibana.

For ElasticSearch and Kibana you will need a working Java machine in your host. Have a look at their installation instructions if needed. But if you have it available, installation is usually straigtforward. Note: you will need Kibana4.

If you need to install ElasticSearch, download and uncompress it, from the ElasticSearch website. Then...

```
$ cd elasticsearch-x.x.x/
# [Configure, if needed]
$ bin/elasticsearch
```

If you need to install Kibana, download and uncompress it, from the ElasticSearch website. Then...

```
$ cd kibana-x.x.x-linux-x64
# [Configure, if needed]
$ bin/kibana
```

# Perceval Retrievers

Perceval is the GrimoireLab component retrieving data from data sources, usually by
interacting with service APIs or logs. A part of it is generic for all data sources, but
most of its code is composed by retrievers. A retriever is a Perceval component
specialized in retrieving data from a specific data source.

## Structure of a retriever

A Perceval retriever is built with three components:

- Client: interacts directly with the data source.
- Backend: orchestrates the fetching process by using the Client.
- CommandLine: defines the arguments to initialize and run the Backend from the command
  line.


Backend and CommandLine extend the abstract classes in
[backend.py](https://github.com/grimoirelab/perceval/blob/master/perceval/backend.py).
They require the definition of several methods:

- Backend:

- `metadata_category(item)` defines the type of the fetched items (e.g., issue, topic,
  channel, etc.)
- `metadata_id(item)` identifies the unique ID of the fetched items (e.g., id of GitHub
  issues, commit SHA for Git, etc.)
- `metadata_updated_on(item)` determines the update time of the fetched items (e.g.,
  updated_at attribute of GitHub issues, committed date for Git, etc.)
- `has_resuming()` returns a boolean value whether the backend supports the resuming of
  the fetch process
- `has_caching()` returns a boolean value whether the backend supports caching items
  during the fetch process.
- `fetch(from_date)` contains the logic to perform the fetching process
- `fetch_from_cache()` contains the logic to perform the fetching process from cache

- CommandLine:

- `setup_cmd_parser()` initializes the command parser for the backend.

All backends have their own unit tests and corresponding data, saved in the folder
[/tests](https://github.com/grimoirelab/perceval/tree/master/tests) and
[/tests/data](https://github.com/grimoirelab/perceval/tree/master/tests/data)
respectively. Since most backends fetch data from HTTP APIs, their tests rely on HTTPretty
(version==0.8.6), a mocking tool that simulates HTTP requests.

## Tips for implementing retrievers

#### Implementation & conventions:
Components are usually implemented incrementally, starting with the `Client`, `Backend`,
and `CommandLine` classes. Client methods are named representing the information returned
by the backend, using nouns instead of verbs. For example: `__issues(..)__` instead of
`__get_issues(...)__`, `__user(...)__` instead of `__get_user(...)__`

#### Tests

Testing is important to ensure that the Perceval retriever is working well:

- Tests are written together with the components, as soon as possible.
- Some tests are run on just a tiny subset of the data source, such as a small set of
  GitHub issues or commits in Git.
- Once the retriever is near complete, stress tests are run too, such as retrieving data
  from very large repositories.

#### Caching

The cache is filled with raw items produced during the fetch process, not JSON documents
produced by the Backend. Fetching data from cache is probably one of the most tricky
activities when implementing a backend. The complexity lays on the fact that the cache,
basically a FIFO queue, stores items which in many cases have a nested tree structure.
This happens because usually items of different kinds are retrieved from the data source.
For example, for an issue tracking system, issues, comments and authors could be
retrieved. This nested structure has to be correctly stored, and later retrieved when
calling the `fetch_from_cache()` method.

A strategy to deal with such a complexity is to add markers before and after pushing items
to the cache. Examples of this strategy have been implemented for
[GitHub](https://github.com/grimoirelab/perceval/blob/master/perceval/backends/core/github.py)
and [Launchpad
backends](https://github.com/grimoirelab/perceval/blob/master/perceval/backends/core/launchpad.py).

The Python-like pseudocode below shows this strategy for extracting issues, comments and
their authors.

```
def fetch():
	...
	raw_issues = client.fetch_issues()
	push_cache_queue('{ISSUES}')
	push_cache_queue(raw_issues)
	
	for issue in json.loads(raw_issues)
		raw_comments = client.fetch_comments(issue)
		push_cache_queue('{COMMENTS}')
		push_cache_queue(raw_comments)
		
		for comment in json.loads(raw_comments)
			raw_author = client.fetch_author(comment)
			push_cache_queue('{AUTHOR}')
			push_cache_queue(raw_author)
			
		push_cache_queue('{ISSUE-END}')
	push_cache_queue('{}{}')
	...
```

```
def fetch_from_cache():
	...
	raw_items = cache.retrieve()
	raw_item = next(raw_items)
	while raw_item != '{}{}'
	
		if raw_item == '{ISSUES}'
			raw_issues = next(raw_items)
			issues = json.loads(raw_issues)
		
			for issue in issues
				raw_item = next(raw_items)
				while raw_item != '{ISSUE-END}'
					if raw_item == '{COMMENTS}'
						raw_comments = next(raw_items)
						comments = json.loads(raw_comments)
						for comment in comments
							tag_author = next(raw_items)
							raw_author = next(raw_items)
					
					raw_item = next(raw_items)
			raw_item = next(raw_items)	
	...
```

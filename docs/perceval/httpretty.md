# Testing with HTTPretty

HTTPretty is a Python mocking tool. It allows for easier testing by providing several
useful features, the most important of which is faking external API data for testing. This
is an important feature for testing, since all tests would break down if the API data
changed. This problem of data contstantly changing or servers going down is solved by
using mocking. A good explanation of what mocking is can be found here on StackOverflow.

## Why test Perceval?

For more information on Perceval’s underlying structure and
functionality, please check the perceval-backends page.

Like any other software, testing Perceval is imperative to its development. Testing is
done with the help of unittest and HTTPretty. Perceval comes into the picture when
fetching data from various data sources is required. Data sources range from pipermail
email archives to the GitHub API. Testing makes it easier to add new functionality or
improve what already exists since tests provide something to fall back on. Tests let you
know how individual parts of the program work and thus makes the code more reliable.

As mentioned above, when it comes to testing the functionality that depends on APIs,
mocking is a strong preference. For example, while testing the data fetched by Perceval
for a repository, say, the number of comments on an issue, testing would be quite
difficult and the tests would have to be updated regularly to keep up with the changing
data. HTTPretty allows “faking” an API by making mock data available at the path from
which Perceval fetches data. Thus, Perceval “fetches” the mock data, which we can test
against the data we actually asked HTTPretty to send to the required path.

## A simple example

The following script depicts a very simple use case of HTTPretty.

```py
import requests
import httpretty

httpretty.enable()

# Using the register_uri function, set method to GET,
# set the uri as shown below, the status to 200
# and the body to HTTPretty.
httpretty.register_uri(
    method=httpretty.GET,
    uri='https://www.example.com',
    status=200,
    body="HTTPretty"
    )

response = requests.get('https://www.example.com') # fetch the info at uri
httpretty.disable() # following code is not affected by the httpretty session
httpretty.reset()   # reset state by removing the uri and history

print(response.text) 
```

```
$ python3 main.py
  'HTTPretty'
```

## Using HTTPretty in Perceval testing

To make it easier to understand, consider the GitHub backend of Perceval. One of the
different categories of data Perceval fetches from the GitHub API is to fetch reviews from
pull requests. For the pull request located at
[/repos///pulls/](https://api.github.com/repos/chaoss/wg-evolution/pulls/12), its reviews
can be found at
[/repos///pulls//reviews](https://api.github.com/repos/chaoss/wg-evolution/pulls/12/reviews).

A possible test for this is mentioned below. It is heavily commented for easier
explanation. The `httpretty.activate` decorator at the top effectively shortens the code,
since — among other things — it performs the following:

- enables the httpretty instance
- deactivates it at the end
- resets it
The it effectively performs the task of `enable()`, `deactivate()` and `reset()`.

```py
@httpretty.activate
def test_pull_reviews(self):
    """Test pull reviews API call"""

    # - The mock data we want Perceval to fetch is placed in files like
    #    github_request_pull_request_1_reviews below. 
    # - read_file is a utility function to read files present in a 
    #    a particular directory.
    pull_request_reviews = read_file('data/github/github_request_pull_request_1_reviews')

    # The API rate limit is read in the same way.
    rate_limit = read_file('data/github/rate_limit')

    # - The httpretty.register_uri method
    #   here is used with the uri: https://api.github.com/rate_limit
    # - The body is the file read above.
    # - forcing_headers allow setting of forced headers on the response. 
    httpretty.register_uri(httpretty.GET,
                           GITHUB_RATE_LIMIT,
                           body=rate_limit,
                           status=200,
                           forcing_headers={
                               'X-RateLimit-Remaining': '20',
                               'X-RateLimit-Reset': '15'
                           })

    # - Just as was done above, the uri: https://api.github.com/repos/
    #   zhquan_example/repo/pulls/1/reviews
    httpretty.register_uri(httpretty.GET,
                           GITHUB_PULL_REQUEST_1_REVIEWS,
                           body=pull_request_reviews,
                           status=200,
                           forcing_headers={
                               'X-RateLimit-Remaining': '20',
                               'X-RateLimit-Reset': '15'
                           })

    # Create a client object with the owner, repo name and tokens required
    client = GitHubClient("zhquan_example", "repo", ["aaa"])

    # A simple assertion to compare the mock data in the file
    # we read at the start and the reviews of the first pull request
    # Perceval fetched from the mock data.
    pull_reviews_raw = [rev for rev in client.pull_reviews(1)]
    self.assertEqual(pull_reviews_raw[0], pull_request_reviews)
```

## Combining HTTPretty with mock attributes

HTTPretty can also be used along with unittest.mock. A good option is to use the
`unittest.mock.patch()` decorator. The object passed to `patch()` is mocked but once the
function is executed, it is returned to its original state, without having to manually
deactivate it.

The line `@unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')` creates a
mock for the `slack.datetime_utcnow` object.

The snippet below is a part of the `test_fetch` function which tests the methods fetching
slack messages. The following uses both HTTPretty and `unittest.mock.patch`.

The method `setup_http_server()` called below uses HTTPretty and is defined
[here](https://github.com/chaoss/grimoirelab-perceval/blob/5f6e7b65a3ef85d738f156a63b3d4f22d36ab8ae/tests/test_slack.py#L56).
It is has a function nested inside it, which is passed as a `Response` object to
`httpretty.register_uri()`.

With the `setup_http_server` function, `http_requests`, variable which stores the value
returned by `setup_http_server` is populated with all previous `HTTPrettyRequest` objects.
The documentation can be found
[here](https://httpretty.readthedocs.io/en/latest/api.html#httprettyrequest).

```py
    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')
    def test_fetch(self, mock_utcnow):
        """Test if it fetches a list of messages"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        # With the setup_http_server function, http_requests is populated with 
        # all previous HTTPrettyRequest objects. The documentation can be found
        # here: https://httpretty.readthedocs.io/en/latest/api.html#httprettyrequest
        http_requests = setup_http_server()

        # create a Slack object with the mentioned parameters and 
        # fetch the messages
        slack = Slack('C011DUKE8', 'aaaa', max_items=5)
        messages = [msg for msg in slack.fetch(from_date=None)]

        # the known results which will be compared with what Perceval fetches
        expected = [
            ("<@U0003|dizquierdo> commented on <@U0002|acs> file>: Thanks.",
             'cc2338c23bf5293308d596629c598cd5ec37d14b',
             1486999900.000000, 'dizquierdo@example.com', 'test channel'),
            ("There are no events this week.",
             'b48fd01f4e010597091b7e44cecfb6074f56a1a6',
             1486969200.000136, 'B0001', 'test channel'),
            ("<@U0003|dizquierdo> has joined the channel",
             'bb95a1facf7d61baaf57322f3d6b6d2d45af8aeb',
             1427799888.0, 'dizquierdo@example.com', 'test channel'),
            ("tengo el m\u00f3vil",
             'f8668de6fadeb5730e0a80d4c8e5d3f8d175f4d5',
             1427135890.000071, 'jsmanrique@example.com', 'test channel'),
            ("hey acs",
             '29c2942a704c4e0b067daeb76edb2f826376cecf',
             1427135835.000070, 'jsmanrique@example.com', 'test channel'),
            ("¿vale?",
             '757e88ea008db0fff739dd261179219aedb84a95',
             1427135740.000069, 'acs@example.com', 'test channel'),
            ("jsmanrique: tenemos que dar m\u00e9tricas super chulas",
             'e92555381bc431a53c0b594fc118850eafd6e212',
             1427135733.000068, 'acs@example.com', 'test channel'),
            ("hi!",
             'b92892e7b65add0e83d0839de20b2375a42014e8',
             1427135689.000067, 'jsmanrique@example.com', 'test channel'),
            ("hi!",
             'e59d9ca0d9a2ba1c747dc60a0904edd22d69e20e',
             1427135634.000066, 'acs@example.com', 'test channel')
        ]

        # The testing is below
        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            expc = expected[x]
            self.assertEqual(message['data']['text'], expc[0])
            self.assertEqual(message['uuid'], expc[1])
            self.assertEqual(message['origin'], 'https://slack.com/C011DUKE8')
            self.assertEqual(message['updated_on'], expc[2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'https://slack.com/C011DUKE8')

            # The second message was sent by a bot
            if x == 1:
                self.assertEqual(message['data']['bot_id'], expc[3])
            else:
                self.assertEqual(message['data']['user_data']['profile']['email'], expc[3])

            self.assertEqual(message['data']['channel_info']['name'], expc[4])
            self.assertEqual(message['data']['channel_info']['num_members'], 164)

            ..
            ..
            .
```

Once we are done with this, we move on to comparing the requests within the same function
we discussed above: `test_fetch`. This part involves using the variable `http_request` we
populated above. Since our expected values, stored in expected below, are in the form of
Python dictionaries, we make use of the `querystring` attribute of `HTTPrettyRequest`
objects.

```py
        expected = [
            {
                'channel': ['C011DUKE8'],
                'token': ['aaaa']
            },
            {
                'channel': ['C011DUKE8'],
                'token': ['aaaa']
            },
            {
                'channel': ['C011DUKE8'],
                'token': ['aaaa'],
                'cursor': ['dXNlcl9pZDpVNEMwUTZGQTc=']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['0'],
                'latest': ['1483228800.0'],
                'token': ['aaaa'],
                'count': ['5']
            },
            {
                'user': ['U0003'],
                'token': ['aaaa']
            },
            {
                'user': ['U0002'],
                'token': ['aaaa']
            },
            {
                'user': ['U0001'],
                'token': ['aaaa']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['0'],
                'latest': ['1427135733.000068'],
                'token': ['aaaa'],
                'count': ['5']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            # - As mentioned above, http_requests is a list of 
            #   HTTPrettyRequest objects.
            # - HTTPretty allows the user to fetch the response body in the 
            #   form of a dictionary by using the `querystring` attribute, as 
            #   shown below.
            self.assertDictEqual(http_requests[i].querystring, expected[i])
```

Thus, HTTPretty is a very handy tool when it comes to testing code, especially when there
are interactions with an API. HTTPretty is an important part of Perceval testing as
discussed above.

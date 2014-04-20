import urllib
import urllib2
import urlparse
import json


class APIClient:
    def __init__(self, api_root):
        self.api_root = api_root

    def __call__(self, path, params, body=None):
        full_url = urlparse.urljoin(self.api_root, path)
        if params:
            params_str = "?" + urllib.urlencode(params)
        else:
            params_str = ""
        full_url += params_str
        if body:
            req = urllib2.Request(full_url, data=json.dumps(body), 
                                  headers={'Content-type': 'application/json'})
        else:
            req = urllib2.Request(full_url,
                                  headers={'Content-type': 'application/json'})

        content = urllib2.urlopen(req).read()
        result = json.loads(content)
        return result

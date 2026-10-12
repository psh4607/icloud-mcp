"""The guard must run before any network I/O, including redirected requests."""
from io import BytesIO
from types import SimpleNamespace
import niquests
import pytest
from niquests.adapters import BaseAdapter
from icloud_mcp.clients import CalendarClient

class FakeAdapter(BaseAdapter):
    def __init__(self, locations=()):
        self.locations = list(locations)
        self.calls = []
    def send(self, request, **kwargs):
        self.calls.append((request, kwargs))
        response = niquests.Response()
        response.request = request
        response.url = request.url
        response.status_code = 307 if self.locations else 200
        if self.locations:
            response.headers['Location'] = self.locations.pop(0)
        response._content = b''
        response.raw = BytesIO(b'')
        return response
    def close(self):
        pass

@pytest.fixture
def guarded(monkeypatch):
    monkeypatch.setattr('icloud_mcp.clients.get_password', lambda *args: 'fake-password')
    monkeypatch.setattr('caldav.DAVClient.principal', lambda self: self)
    settings = SimpleNamespace(username='test@example.com',keyring_service='test',caldav_url='https://caldav.icloud.com/')
    client = CalendarClient(settings)
    dav = client.principal()
    adapter = FakeAdapter()
    dav.session.mount('https://', adapter)
    dav.session.mount('http://', adapter)
    yield dav, adapter
    client.close()

@pytest.mark.parametrize('url',[
 'http://caldav.icloud.com/', 'https://evil.example/',
 'https://caldav.icloud.com.evil.example/', 'https://evilicloud.com/',
 'https://user:password@caldav.icloud.com/', 'https://caldav.icloud.com:444/',
 'https://contacts.icloud.com/', 'https://127.0.0.1/',
])
def test_blocks_unapproved_hosts_before_network(guarded,url):
    dav, adapter = guarded
    with pytest.raises(ValueError):
        dav.session.request('PROPFIND',url)
    assert not adapter.calls

@pytest.mark.parametrize('method',['PUT','DELETE','POST','MKCALENDAR','PROPPATCH','MOVE'])
def test_blocks_writes_at_transport(guarded,method):
    dav,adapter=guarded
    with pytest.raises(ValueError):
        dav.session.request(method,'https://caldav.icloud.com/')
    assert not adapter.calls

@pytest.mark.parametrize('target',['https://evil.example/','http://p01-caldav.icloud.com/'])
def test_redirect_is_checked_before_following(guarded,target):
    dav,adapter=guarded
    adapter.locations=[target]
    with pytest.raises(ValueError):
        dav.session.request('PROPFIND','https://caldav.icloud.com/')
    assert len(adapter.calls)==1


def test_allows_apple_partition_redirect_with_tls_and_no_proxy(guarded,monkeypatch):
    dav,adapter=guarded
    monkeypatch.setenv('HTTPS_PROXY','http://evil.example:8080')
    adapter.locations=['https://p123-caldav.icloud.com/account/']
    dav.session.request('PROPFIND','https://caldav.icloud.com/',auth=('test','fake-password'))
    assert len(adapter.calls)==2
    for req,options in adapter.calls:
        assert options['verify'] is True
        assert not options['proxies']
        assert 'Authorization' in req.headers
    assert dav.session.trust_env is False


def test_cannot_disable_tls_validation(guarded):
    dav,adapter=guarded
    with pytest.raises(ValueError):
        dav.session.request('GET','https://caldav.icloud.com/',verify=False)
    assert not adapter.calls


def test_no_unguarded_revocation_or_alternate_port_connections(guarded):
    from niquests.utils import should_check_ocsp, should_check_crl
    dav, adapter = guarded
    # A peer certificate may name arbitrary OCSP/CRL servers. Those helpers
    # use independent transports and must not make outbound HTTP requests.
    connection = SimpleNamespace(certificate_der=b'fake', certificate_dict={'OCSP': ('http://ca.example/',), 'crlDistributionPoints': ('http://ca.example/',)})
    assert not should_check_ocsp(connection, dav.session._revocation_configuration)
    assert not should_check_crl(connection, dav.session._revocation_configuration)
    assert dav.session._disable_http3 is True
    assert dav.session._disable_http2 is True

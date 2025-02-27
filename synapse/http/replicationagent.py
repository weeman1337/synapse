# Copyright 2023 The Matrix.org Foundation C.I.C.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from typing import Optional

from zope.interface import implementer

from twisted.internet import defer
from twisted.internet.endpoints import HostnameEndpoint, wrapClientTLS
from twisted.internet.interfaces import IStreamClientEndpoint
from twisted.python.failure import Failure
from twisted.web.client import URI, HTTPConnectionPool, _AgentBase
from twisted.web.error import SchemeNotSupported
from twisted.web.http_headers import Headers
from twisted.web.iweb import (
    IAgent,
    IAgentEndpointFactory,
    IBodyProducer,
    IPolicyForHTTPS,
    IResponse,
)

from synapse.types import ISynapseReactor

logger = logging.getLogger(__name__)


@implementer(IAgentEndpointFactory)
class ReplicationEndpointFactory:
    """Connect to a given TCP socket"""

    def __init__(
        self,
        reactor: ISynapseReactor,
        context_factory: IPolicyForHTTPS,
    ) -> None:
        self.reactor = reactor
        self.context_factory = context_factory

    def endpointForURI(self, uri: URI) -> IStreamClientEndpoint:
        """
        This part of the factory decides what kind of endpoint is being connected to.

        Args:
            uri: The pre-parsed URI object containing all the uri data

        Returns: The correct client endpoint object
        """
        if uri.scheme in (b"http", b"https"):
            endpoint = HostnameEndpoint(self.reactor, uri.host, uri.port)
            if uri.scheme == b"https":
                endpoint = wrapClientTLS(
                    self.context_factory.creatorForNetloc(uri.host, uri.port), endpoint
                )
            return endpoint
        else:
            raise SchemeNotSupported(f"Unsupported scheme: {uri.scheme!r}")


@implementer(IAgent)
class ReplicationAgent(_AgentBase):
    """
    Client for connecting to replication endpoints via HTTP and HTTPS.

    Much of this code is copied from Twisted's twisted.web.client.Agent.
    """

    def __init__(
        self,
        reactor: ISynapseReactor,
        contextFactory: IPolicyForHTTPS,
        connectTimeout: Optional[float] = None,
        bindAddress: Optional[bytes] = None,
        pool: Optional[HTTPConnectionPool] = None,
    ):
        """
        Create a ReplicationAgent.

        Args:
            reactor: A reactor for this Agent to place outgoing connections.
            contextFactory: A factory for TLS contexts, to control the
                verification parameters of OpenSSL.  The default is to use a
                BrowserLikePolicyForHTTPS, so unless you have special
                requirements you can leave this as-is.
            connectTimeout: The amount of time that this Agent will wait
                for the peer to accept a connection.
            bindAddress: The local address for client sockets to bind to.
            pool: An HTTPConnectionPool instance, or None, in which
                case a non-persistent HTTPConnectionPool instance will be
                created.
        """
        _AgentBase.__init__(self, reactor, pool)
        endpoint_factory = ReplicationEndpointFactory(reactor, contextFactory)
        self._endpointFactory = endpoint_factory

    def request(
        self,
        method: bytes,
        uri: bytes,
        headers: Optional[Headers] = None,
        bodyProducer: Optional[IBodyProducer] = None,
    ) -> "defer.Deferred[IResponse]":
        """
        Issue a request to the server indicated by the given uri.

        An existing connection from the connection pool may be used or a new
        one may be created.

        Currently, HTTP and HTTPS schemes are supported in uri.

        This is copied from twisted.web.client.Agent, except:

        * It uses a different pool key (combining the host & port).
        * It does not call _ensureValidURI(...) since it breaks on some
          UNIX paths.

        See: twisted.web.iweb.IAgent.request
        """
        parsedURI = URI.fromBytes(uri)
        try:
            endpoint = self._endpointFactory.endpointForURI(parsedURI)
        except SchemeNotSupported:
            return defer.fail(Failure())

        # This sets the Pool key to be:
        #  (http(s), <host:ip>)
        key = (parsedURI.scheme, parsedURI.netloc)

        # _requestWithEndpoint comes from _AgentBase class
        return self._requestWithEndpoint(
            key,
            endpoint,
            method,
            parsedURI,
            headers,
            bodyProducer,
            parsedURI.originForm,
        )

import unittest

from contextlib import contextmanager
from itertools import chain
from mock import Mock, patch

import smarkets.eto.piqi_pb2 as eto
import smarkets.seto.piqi_pb2 as seto

from smarkets.clients import Callback, Smarkets


class CallbackTestCase(unittest.TestCase):
    "Test the `smarkets.Callback` class"
    def setUp(self):
        "Set up the tests"
        self.callback = Callback()

    def tearDown(self):
        "Tear down the test requirements"
        self.callback = None

    def test_simple_fire(self):
        "Test the simple case where the handler fires"
        handler = Mock()
        self.callback += handler
        self.assertFalse(handler.called)
        self.assertEquals(1, len(self.callback))
        self.callback('foo')
        handler.assert_called_once_with('foo')
        self.assertEquals(1, len(self.callback))

    def test_unhandle(self):
        "Test the case where a handler is removed"
        handler = Mock()
        self.callback += handler
        self.assertFalse(handler.called)
        self.assertEquals(1, len(self.callback))
        self.callback -= handler
        self.assertEquals(0, len(self.callback))
        self.callback('foo')
        self.assertFalse(handler.called)

    def test_2_handlers(self):
        "Test 2 handlers both get called"
        handler1 = Mock()
        handler2 = Mock()
        self.callback += handler1
        self.callback += handler2
        self.assertFalse(handler1.called)
        self.assertFalse(handler2.called)
        self.assertEquals(2, len(self.callback))
        self.callback('foo')
        handler1.assert_called_once_with('foo')
        handler2.assert_called_once_with('foo')
        self.assertEquals(2, len(self.callback))

    def test_many_handlers(self):
        "General version of `test_2_handlers`"
        handlers = [Mock() for _ in xrange(1, 100)]
        for handler in handlers:
            self.callback += handler
        self.assertEquals(len(handlers), len(self.callback))
        for handler in handlers:
            self.assertFalse(handler.called)
        self.callback('foo')
        for handler in handlers:
            handler.assert_called_once_with('foo')
        self.assertEquals(len(handlers), len(self.callback))

    def test_many_unhandle(self):
        "Unhandle many"
        real_handlers = [Mock() for _ in xrange(1, 100)]
        to_unhandle = [Mock() for _ in xrange(1, 20)]
        for handler in chain(real_handlers, to_unhandle):
            self.callback += handler
        self.assertEquals(
            len(real_handlers) + len(to_unhandle), len(self.callback))
        for handler in to_unhandle:
            self.callback -= handler
        self.assertEquals(len(real_handlers), len(self.callback))
        self.callback('foo')
        for handler in to_unhandle:
            self.assertFalse(handler.called)
        for handler in real_handlers:
            handler.assert_called_once_with('foo')

    def test_handle_exception(self):
        "Test that an exception is raised by the callback method"
        handler = Mock(side_effect=self._always_raise)
        self.callback += handler
        self.assertRaises(Exception, self.callback, 'foo')

    def test_2_handle_exception(self):
        "Test that an exception is raised by the callback method"
        handler1 = Mock(side_effect=self._always_raise)
        handler2 = Mock()
        self.callback += handler1
        self.callback += handler2
        self.assertRaises(Exception, self.callback, 'foo')
        # Because the collection of handlers in the `Callback` is a
        # `set` the 'firing' order is undefined. However, if handler2
        # is called, we assert that it is called correctly here.
        if handler2.called:
            handler2.assert_called_once_with('foo')

    @staticmethod
    def _always_raise(*args, **kwargs):
        "Always raise `Exception` with no arguments"
        raise Exception()


class SmarketsTestCase(unittest.TestCase):
    "Tests for the `smarkets.Smarkets` client object"
    def setUp(self):
        "Patch the `Session` object for mock use"
        self.session_patcher = patch('smarkets.sessions.Session')
        self.mock_session_cls = self.session_patcher.start()
        self.mock_session = self.mock_session_cls.return_value
        self.client = Smarkets(self.mock_session)

    def tearDown(self):
        "Stop the patcher"
        self.session_patcher.stop()
        self.mock_session_cls = None
        self.mock_session = None
        self.client = None

    def test_login(self):
        "Test the `Smarkets.login` method"
        payload = self._login_response()
        self.mock_session.next_frame.return_value = payload
        response = Mock()
        self.client.add_handler('eto.login_response', response)
        self.client.login()
        self.assertEquals(1, self.mock_session.connect.call_count)
        self.assertEquals(1, self.mock_session.next_frame.call_count)
        response.assert_called_once_with(payload)

    def test_login_norecv(self):
        "Test the `Smarkets.login` method"
        payload = self._login_response()
        self.mock_session.next_frame.return_value = payload
        response = Mock()
        self.client.add_handler('eto.login_response', response)
        self.client.login(False)
        self.assertEquals(1, self.mock_session.connect.call_count)
        self.assertFalse(self.mock_session.next_frame.called)
        self.assertFalse(response.called)
        self.client.read()
        self.assertEquals(1, self.mock_session.next_frame.call_count)
        response.assert_called_once_with(payload)

    def test_logout(self):
        "Test the `Smarkets.logout` method"
        self.client.logout()
        self.assertEquals(1, self.mock_session.disconnect.call_count)

    def test_flush(self):
        "Test the `Smarkets.flush` method"
        self.client.flush()
        self.assertEquals(1, self.mock_session.flush.call_count)

    def test_order(self):
        "Test the `Smarkets.order` method"
        market_id = self.client.str_to_uuid128('1c024')
        contract_id = self.client.str_to_uuid128('1cccc')
        with self._clear_send():
            self.client.order(10000, 2500, seto.SIDE_BUY, market_id, contract_id)

    def test_order_cancel(self):
        "Test the `Smarkets.order_cancel` method"
        order_id = self.client.str_to_uuid128('1fff0')
        with self._clear_send():
            self.client.order_cancel(order_id)

    def test_ping(self):
        "Test the `Smarkets.ping` method"
        with self._clear_send():
            self.client.ping()

    def test_subscribe(self):
        "Test the `Smarkets.subscribe` method"
        market_id = self.client.str_to_uuid128('1c024')
        with self._clear_send():
            self.client.subscribe(market_id)

    def test_unsubscribe(self):
        "Test the `Smarkets.unsubscribe` method"
        market_id = self.client.str_to_uuid128('1c024')
        with self._clear_send():
            self.client.unsubscribe(market_id)

    def test_request_events(self):
        "Test the `Smarkets.request_events` method"
        with patch('smarkets.events.Politics') as mock_politics:
            request = mock_politics.return_value
            with self._clear_send():
                self.client.request_events(request)
            request.copy_to.assert_called_once_with(
                self.mock_session.out_payload)

    def test_fetch_http_found(self):
        "Test the `Smarkets.fetch_http_found` method"
        mock_fetch = Mock()
        self.client.fetch = mock_fetch
        expected = seto.Events()
        payload_bytes = expected.SerializeToString()
        mock_fetch.return_value = ('application/x-protobuf', payload_bytes)
        payload = seto.Payload()
        payload.type = seto.PAYLOAD_HTTP_FOUND
        payload.http_found.url = 'http://domain.invalid/url'
        payload.http_found.seq = 2
        self.assertEqual(expected, self.client.fetch_http_found(payload))
        mock_fetch.assert_called_once_with(payload.http_found.url)

    @contextmanager
    def _clear_send(self):
        """
        Shortcut for asserting that the outgoing payload is cleared
        and sent via the session
        """
        self.mock_session.out_payload.Clear = Mock()
        yield
        self.mock_session.send.assert_called_once_with(True)
        self.assertEquals(1, self.mock_session.out_payload.Clear.call_count)

    @staticmethod
    def _login_response():
        "Create a dummy login response payload"
        payload = seto.Payload()
        payload.eto_payload.seq = 1
        payload.eto_payload.type = eto.PAYLOAD_LOGIN_RESPONSE
        payload.eto_payload.login_response.session = 'session'
        payload.eto_payload.login_response.reset = 2
        return payload
# encoding: utf-8
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for utils."""

import datetime
import os
import tempfile
import unittest

import django.utils.translation
from google.appengine.ext import db
from google.appengine.ext import testbed
from google.appengine.ext import webapp
from pytest import raises

import config
import pfif
import main
import model
import resources
import utils


class UtilsTests(unittest.TestCase):
    """Test the loose odds and ends."""

    def test_get_app_name(self):
        app_id = 'test'
        os.environ['APPLICATION_ID'] = app_id
        assert utils.get_app_name() == app_id
        os.environ['APPLICATION_ID'] = 's~' + app_id
        assert utils.get_app_name() == app_id

    def test_get_host(self):
        host = 'foo.appspot.com'
        os.environ['HTTP_HOST'] = host
        assert utils.get_host() == host
        os.environ['HTTP_HOST'] = 'foo.' + host
        assert utils.get_host() == host

    def test_encode(self):
        assert utils.encode('abc') == 'abc'
        assert utils.encode(u'abc') == 'abc'
        assert utils.encode(u'\u4f60\u597d') == '\xe4\xbd\xa0\xe5\xa5\xbd'
        assert utils.encode('\xe4\xbd\xa0\xe5\xa5\xbd') == \
            '\xe4\xbd\xa0\xe5\xa5\xbd'
        assert utils.encode('abc', 'shift_jis') == 'abc'
        assert utils.encode(u'abc', 'shift_jis') == 'abc'
        assert utils.encode(u'\uffe3\u2015', 'shift_jis') == '\x81P\x81\\'

    def test_urlencode(self):
        assert utils.urlencode({'foo': 'bar',
                                'skipped': (),
                                'a param with space': 'value',
                                'x': 'a value with space'}) == \
            'a+param+with+space=value&foo=bar&x=a+value+with+space'
        assert utils.urlencode({'a': u'foo',
                                'b': u'\u4f60\u597d',
                                'c': '\xe4\xbd\xa0\xe5\xa5\xbd',
                                u'\u4f60\u597d': 'd'}) == \
            'a=foo&b=%E4%BD%A0%E5%A5%BD' + \
            '&c=%E4%BD%A0%E5%A5%BD&%E4%BD%A0%E5%A5%BD=d'

    def test_set_url_param(self):
        assert utils.set_url_param(
            'http://example.com/server/', 'foo', 'bar') == \
            'http://example.com/server/?foo=bar'
        assert utils.set_url_param(
            'http://example.com/server', 'foo', 'bar') == \
            'http://example.com/server?foo=bar'
        assert utils.set_url_param(
            'http://example.com/server?foo=baz', 'foo', 'bar') == \
            'http://example.com/server?foo=bar'
        assert utils.set_url_param(
            'http://example.com/server?foo=baz', 'foo', 'bar') == \
            'http://example.com/server?foo=bar'

        # Collapses multiple parameters
        assert utils.set_url_param(
            'http://example.com/server?foo=baz&foo=baq', 'foo', 'bar') == \
            'http://example.com/server?foo=bar'
        assert utils.set_url_param(
            'http://example.com/server?foo=baz&foo=baq', 'x', 'y') == \
            'http://example.com/server?foo=baq&x=y'

        # Unicode is properly converted
        assert utils.set_url_param(
            'http://example.com/server?foo=bar',
            u'\u4f60\u597d', '\xe4\xbd\xa0\xe5\xa5\xbd') == \
            'http://example.com/server?foo=bar&' + \
            '%E4%BD%A0%E5%A5%BD=%E4%BD%A0%E5%A5%BD'

    def test_strip(self):
        assert utils.strip('    ') == ''
        assert utils.strip(u'    ') == u''
        assert utils.strip('  x  ') == 'x'
        assert utils.strip(u'  x  ') == u'x'
        raises(Exception, utils.strip, None)

    def test_validate_yes(self):
        assert utils.validate_yes('yes') == 'yes'
        assert utils.validate_yes('YES') == 'yes'
        assert utils.validate_yes('no') == ''
        assert utils.validate_yes('y') == ''
        raises(Exception, utils.validate_yes, None)

    def test_validate_role(self):
        assert utils.validate_role('provide') == 'provide'
        assert utils.validate_role('PROVIDE') == 'provide'
        assert utils.validate_role('seek') == 'seek'
        assert utils.validate_role('pro') == 'seek'
        assert utils.validate_role('provider') == 'seek'
        raises(Exception, utils.validate_role, None)

    def test_validate_expiry(self):
        assert utils.validate_expiry(100) == 100
        assert utils.validate_expiry('abc') == None
        assert utils.validate_expiry(-100) == None

    def test_validate_email(self):
        # These email addresses are correct
        email = 'test@example.com'
        assert utils.validate_email(email) == True
        email = 'test2@example.com'
        assert utils.validate_email(email) == True
        email = 'test3.test@example.com'
        assert utils.validate_email(email) == True
        email = 'test4.test$test@example.com'
        assert utils.validate_email(email) == True
        email = 'test6.test$test%test@example.com'
        assert utils.validate_email(email) == True
        email = ('test7.test@domain.whywouldyoueventwantatldthislonggoodgrief'
                 'thisisprettyridiculous')
        assert utils.validate_email(email) == True

        # These email addresses are incorrect
        email = 'test@example'
        assert utils.validate_email(email) == False
        email = 'test.com'
        assert utils.validate_email(email) == False
        email = 'usernamenoatsymbol.com'
        assert utils.validate_email(email) == False
        email = ('test@domain.thistldistoolongasitssixtyfourcharactersandthere'
                 'arerulesafterall')
        assert utils.validate_email(email) == False

        # Empty string instead of email address
        email = ''
        assert utils.validate_email(email) == None

    def test_validate_version(self):
        for version in pfif.PFIF_VERSIONS:
            assert utils.validate_version(version) == pfif.PFIF_VERSIONS[
                version]
        assert utils.validate_version('') == pfif.PFIF_VERSIONS[
            pfif.PFIF_DEFAULT_VERSION]
        raises(Exception, utils.validate_version, '1.0')

    def test_validate_age(self):
        assert utils.validate_age('20') == '20'
        assert utils.validate_age(' 20 ') == '20'
        assert utils.validate_age(u'??????') == '20'
        assert utils.validate_age('20-30') == '20-30'
        assert utils.validate_age('20 - 30') == '20-30'
        assert utils.validate_age(u'???????????????') == '20-30'
        assert utils.validate_age(u'?????????????????????') == '20-30'
        assert utils.validate_age('20 !') == ''
        assert utils.validate_age('2 0') == ''

    # TODO: test_validate_image

    def test_fuzzify_age(self):
        assert utils.fuzzify_age('20') == '20-25'
        assert utils.fuzzify_age('22') == '20-25'
        assert utils.fuzzify_age('21-22') == '20-25'
        assert utils.fuzzify_age('40-48') == '40-48'
        assert utils.fuzzify_age('40-40') == '40-45'
        assert utils.fuzzify_age(None) == None
        assert utils.fuzzify_age('banana') == None

    def test_set_utcnow_for_test(self):
        max_delta = datetime.timedelta(0,0,100)
        utcnow = datetime.datetime.utcnow()
        utilsnow = utils.get_utcnow()
        # max sure we're getting the current time.
        assert (utilsnow - utcnow) < max_delta
        # now set the utils time.
        test_time = datetime.datetime(2011, 1, 1, 0, 0)
        utils.set_utcnow_for_test(test_time)
        assert utils.get_utcnow() == test_time
        # now unset.
        utils.set_utcnow_for_test(None)
        assert utils.get_utcnow()
        assert utils.get_utcnow() != test_time


class HandlerTests(unittest.TestCase):
    """Tests for the base handler implementation."""

    def setUp(self):
        # Make it look like the dev server so HTTPS isn't required.
        os.environ['APPLICATION_ID'] = 'dev~abc'
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_user_stub()
        model.Repo(key_name='haiti').put()
        config.set_for_repo(
            'haiti',
            repo_titles={'en': 'Haiti Earthquake'},
            language_menu_options=['en', 'ht', 'fr', 'es'],
            referrer_whitelist=[])
        self.original_get_rendered = resources.get_rendered

    def tearDown(self):
        db.delete(config.ConfigEntry.all())
        resources.get_rendered = self.original_get_rendered
        self.testbed.deactivate()

    def handler_for_url(self, url):
        request = webapp.Request(webapp.Request.blank(url).environ)
        response = webapp.Response()
        handler = utils.BaseHandler(request, response, main.setup_env(request))
        return (request, response, handler)

    def test_parameter_validation(self):
        _, _, handler = self.handler_for_url(
            '/haiti/start?'
            'given_name=++John++&'
            'family_name=Doe&'
            'author_made_contact=YES&'
            'role=PROVIDE&')

        assert handler.params.given_name == 'John'
        assert handler.params.family_name == 'Doe'
        assert handler.params.author_made_contact == 'yes'
        assert handler.params.role == 'provide'

    def test_whitelisted_referrer(self):
        config.set_for_repo('haiti', referrer_whitelist=['a.org'])
        _, _, handler = self.handler_for_url(
            '/haiti?referrer=a.org')
        assert handler.params.referrer == 'a.org'

    def test_nonwhitelisted_referrer(self):
        _, _, handler = self.handler_for_url(
            '/haiti?referrer=foobar')
        assert handler.params.referrer == ''

    def test_nonexistent_repo(self):
        request, response, handler = self.handler_for_url('/x/start')
        assert response.status_int == 404
        assert 'No such repository' in response.body
        assert 'class="error"' in response.body  # error template

    def test_set_allow_believed_dead_via_ui(self):
        """Verify the configuration of allow_believed_dead_via_ui."""
        # Set allow_believed_dead_via_ui to be True
        config.set_for_repo('haiti', allow_believed_dead_via_ui=True)
        _, response, handler = self.handler_for_url('/haiti/start')
        assert handler.config.allow_believed_dead_via_ui == True

        # Set allow_believed_dead_via_ui to be False
        config.set_for_repo('haiti', allow_believed_dead_via_ui=False)
        _, response, handler = self.handler_for_url('/haiti/start')
        assert handler.config.allow_believed_dead_via_ui == False

    def test_error_message(self):
        """Regression test for an XSS vulnerability."""
        resources.get_rendered = lambda: 1/0  # force error template to fail

        request, response, handler = self.handler_for_url('/?lang=<script>&')
        assert 'Invalid language tag' in response.body
        assert '<script' not in response.body

    def test_should_show_inline_photo(self):
        _, _, handler = self.handler_for_url('/haiti/create')
        # localhost is the base URL for handlers in the test environment
        assert handler.should_show_inline_photo(
            'http://localhost/photo.jpg')
        assert not handler.should_show_inline_photo(
            'http://www.example.com/photo.jpg')

    def test_filter_sensitive_fields_in_person_record(self):
        """Test passing a person recrod to utils.filter_sensitive_fields().
        """
        person_record = {
            'person_record_id': 'person.1',
            'full_name': 'Taro Yamada',
            'date_of_birth': '2000-01-01',
            'author_email': 'taro@example.com',
            'author_phone': '01234567890',
        }
        utils.filter_sensitive_fields([person_record])
        assert person_record['person_record_id'] == 'person.1'
        assert person_record['full_name'] == 'Taro Yamada'
        assert person_record['date_of_birth'] == ''
        assert person_record['author_email'] == ''
        assert person_record['author_phone'] == ''

    def test_filter_sensitive_fields_in_note_record(self):
        """Test passing a note recrod to utils.filter_sensitive_fields().
        """
        note_record = {
            'note_record_id': 'note.1',
            'person_record_id': 'person.1',
            'status': 'is_note_author',
            'text': 'I am safe',
            'author_email': 'taro@example.com',
            'author_phone': '01234567890',
        }
        utils.filter_sensitive_fields([note_record])
        assert note_record['note_record_id'] == 'note.1'
        assert note_record['person_record_id'] == 'person.1'
        assert note_record['status'] == 'is_note_author'
        assert note_record['text'] == 'I am safe'
        assert note_record['author_email'] == ''
        assert note_record['author_phone'] == ''

    def test_filter_sensitive_fields_in_joined_record(self):
        """Test passing a joined recrod of a person and a note to
        utils.filter_sensitive_fields().
        """
        joined_record = {
            'person_record_id': 'person.1',
            'person_full_name': 'Taro Yamada',
            'person_date_of_birth': '2000-01-01',
            'person_author_email': 'taro@example.com',
            'person_author_phone': '01234567890',
            'note_record_id': 'note.1',
            'note_status': 'is_note_author',
            'note_text': 'I am safe',
            'note_author_email': 'taro@example.com',
            'note_author_phone': '01234567890',
        }
        utils.filter_sensitive_fields([joined_record])
        assert joined_record['person_record_id'] == 'person.1'
        assert joined_record['person_full_name'] == 'Taro Yamada'
        assert joined_record['person_date_of_birth'] == ''
        assert joined_record['person_author_email'] == ''
        assert joined_record['person_author_phone'] == ''
        assert joined_record['note_record_id'] == 'note.1'
        assert joined_record['note_status'] == 'is_note_author'
        assert joined_record['note_text'] == 'I am safe'
        assert joined_record['note_author_email'] == ''
        assert joined_record['note_author_phone'] == ''

    def test_join_person_and_note_record(self):
        """Test passing a person and note recrod to
        utils.join_person_and_note_record().
        """
        person_record = {
            'person_record_id': 'person.1',
            'full_name': 'Taro Yamada',
        }
        note_record = {
            'note_record_id': 'note.1',
            'person_record_id': 'person.1',
            'status': 'is_note_author',
        }
        joined_record = utils.join_person_and_note_record(
            person_record, note_record)
        assert joined_record['person_record_id'] == 'person.1'
        assert joined_record['person_full_name'] == 'Taro Yamada'
        assert joined_record['note_record_id'] == 'note.1'
        assert joined_record['note_status'] == 'is_note_author'

    def test_join_person_and_none_note_record(self):
        """Test passing None as a note record to
        utils.join_person_and_note_record().
        """
        person_record = {
            'person_record_id': 'person.1',
            'full_name': 'Taro Yamada',
        }
        joined_record = utils.join_person_and_note_record(
            person_record, None)
        assert joined_record['person_record_id'] == 'person.1'
        assert joined_record['person_full_name'] == 'Taro Yamada'

    def test_get_field_name_for_joined_record(self):
        assert (
          utils.get_field_name_for_joined_record('full_name', 'person')
              == 'person_full_name')
        assert (
          utils.get_field_name_for_joined_record('status', 'note')
              == 'note_status')

        # person_record_id and note_record_id don't change.
        assert (
          utils.get_field_name_for_joined_record('person_record_id', 'person')
              == 'person_record_id')
        assert (
          utils.get_field_name_for_joined_record('note_record_id', 'note')
              == 'note_record_id')
        assert (
          utils.get_field_name_for_joined_record('person_record_id', 'note')
              == 'person_record_id')


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python

import cgi
import os
import httplib2
import oauth2 as oauth

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.ext.webapp import util

from xml.dom import minidom

eventUrlTemplate = "https://www.appdirect.com/AppDirect/rest/api/events/%s";
consumer_key = '[Put consumer key here]'
consumer_secret = '[Put consumer secret here]'

def signedfetch(token):
    consumer = oauth.Consumer(consumer_key, consumer_secret)
    client = oauth.Client(consumer)
    eventUrl = eventUrlTemplate % token
    return client.request(eventUrl)

class User(db.Model):
    email = db.StringProperty()
    first = db.StringProperty()
    last = db.StringProperty()
    openid = db.StringProperty()

class Event(db.Model):
    date = db.DateTimeProperty(auto_now_add=True)
    token = db.StringProperty()
    url = db.StringProperty()
    status = db.IntegerProperty()
    result = db.TextProperty()

class MainHandler(webapp.RequestHandler):
    def get(self):
        event_query = Event.all().order('-date')
        events = event_query.fetch(10)
        template_values = { 'events' : events }
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))

class UserlistHandler(webapp.RequestHandler):
    def get(self):
        user_query = User.all()
        users = user_query.fetch(100)
        template_values = { 'users' : users }
        path = os.path.join(os.path.dirname(__file__), 'users.html')
        self.response.out.write(template.render(path, template_values))

def Assign(eventHandler, document):
    event = document.getElementsByTagName('event')[0]
    payload = event.getElementsByTagName('payload')[0]
    userXml = payload.getElementsByTagName('user')[0]
    first = userXml.getElementsByTagName('firstName')[0].childNodes[0].data
    last = userXml.getElementsByTagName('lastName')[0].childNodes[0].data
    email = userXml.getElementsByTagName('email')[0].childNodes[0].data
    openid = userXml.getElementsByTagName('openId')[0].childNodes[0].data
    user = User.get_or_insert(openid)
    user.email = email
    user.openid = openid
    user.first = first
    user.last = last
    user.put()

def Unassign(eventHandler, document):
    event = document.getElementsByTagName('event')[0]
    payload = event.getElementsByTagName('payload')[0]
    userXml = payload.getElementsByTagName('user')[0]
    openid = userXml.getElementsByTagName('openId')[0].childNodes[0].data
    query = User.all()
    query.filter('openid =', openid)
    results = query.fetch(1)
    for result in results:
        result.delete()

class EventHandler(webapp.RequestHandler):
    def get(self):
        self.post()

    def post(self):
        event = Event()
        event.token = self.request.get('token')
        event.url = self.request.get('returnUrl')
        resp, content = signedfetch(event.token)
        event.status = int(resp['status'])
        if event.status == 200:
            document = minidom.parseString(content)
            eventType = document.getElementsByTagName('type')[0].childNodes[0].data
            event.result = cgi.escape(document.toprettyxml())
        event.put()
        if eventType == 'USER_ASSIGNMENT':
            Assign(self, document)
            self.response.out.write("""
<result>
   <success>true</success>
   <message>User assigned successfully.</message>
</result>
""")
        elif eventType == 'USER_UNASSIGNMENT':
            Unassign(self, document)
            self.response.out.write("""
<result>
   <success>true</success>
   <message>User unassigned successfully.</message>
</result>
""")
        else:
            self.redirect('/')

def main():
    application = webapp.WSGIApplication([('/', MainHandler),
                                          ('/users', UserlistHandler),
                                          ('/event', EventHandler)],
                                         debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()

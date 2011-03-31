#!/usr/bin/env python

import cgi
import logging
import oauth2

from models import Event
from models import CompanySubscription
from models import User

from google.appengine.api.datastore_errors import BadArgumentError
from xml.dom import minidom

# These credentials are just local. Okay to check into Git.
consumer_key = 'fake-python-isv-307'
consumer_secret = 'hSZr5yppYjHUYOuS'
eventUrlTemplate = "http://localhost:8080/AppDirect/rest/api/events/%s";

errorTemplate = """
<result>
   <success>false</success>
   <errorCode>%s</errorCode>
   <message>%s</message>
</result>
"""

successMessage = """<result><success>true</success></result>"""

def EventFetch(token):
    consumer = oauth2.Consumer(consumer_key, consumer_secret)
    client = oauth2.Client(consumer)
    eventUrl = eventUrlTemplate % token
    resp, content = client.request(eventUrl)
    event = Event()
    event.token = token
    event.status = int(resp['status'])
    if event.status == 200:
        xmlDocument = minidom.parseString(content)
        event.result = cgi.escape(xmlDocument.toprettyxml())
        event.put()
        return ParseEvent(xmlDocument)
    else:
        message = "HTTP response %d" % event.status
        logging.error(message)
        event.put()
        return errorTemplate % ( "UNKNOWN_ERROR", message)

def ParseEvent(xmlDocument):
    eventType = \
        xmlDocument.getElementsByTagName('type')[0].childNodes[0].data
    logging.info("Recevied event type %s" % eventType)
    if eventType == "SUBSCRIPTION_ORDER":
        return CreateOrder(xmlDocument)
    elif eventType == "SUBSCRIPTION_CHANGE":
        return ChangeOrder(xmlDocument)
    elif eventType == "SUBSCRIPTION_CANCEL":
        return CancelOrder(xmlDocument)
    elif eventType == "USER_ASSIGNMENT":
        return AssignUser(xmlDocument)
    elif eventType == "USER_UNASSIGNMENT":
        return UnassignUser(xmlDocument)
    else:
        message = "Event type %s is not configured" % eventType
        return errorTemplate % ( "CONFIGURATION_ERROR", message)
    return successMessage

# XML Parsing utility methods

def GetEvent(xmlDocument):
    return xmlDocument.getElementsByTagName('event')[0]

def GetPayload(xmlDocument):
    return GetEvent(xmlDocument).getElementsByTagName('payload')[0]

def GetAccountIdentifier(payload):
    account = payload.getElementsByTagName('account')[0]
    accountIdentifier = payload.getElementsByTagName('accountIdentifier')[0]\
        .childNodes[0].data
    return accountIdentifier

def GetUserField(userXml, field):
    return userXml.getElementsByTagName(field)[0].childNodes[0].data

# Datatstore utility method

def CreateUser(userXml, companySubscription):
    first = GetUserField(userXml, 'firstName')
    last = GetUserField(userXml, 'lastName')
    email = GetUserField(userXml, 'email')
    openid = GetUserField(userXml, 'openId')
    user = User.get_or_insert(openid)
    user.email = email
    user.openid = openid
    user.first = first
    user.last = last
    user.subscription = companySubscription
    return user

def GetSubscription(accountIdentifier):
    subscription = None
    try:
        subscription = CompanySubscription.get_by_id(int(accountIdentifier))
        logging.info("Found subscription: %s", accountIdentifier)
    except ValueError:
        logging.error("Bad account identifier %s" % accountIdentifier)
    except BadArgumentError:
        logging.error("Bad account identifier %s" % accountIdentifier)
    return subscription

def GetUsers(subscription, openid = None):
    userQuery = User.all()
    userQuery.filter('subscription =', subscription)
    if (openid != None):
        userQuery.filter('openid = ', openid)
    return userQuery

# Event handling methods

def CreateOrder(xmlDocument):
    event = GetEvent(xmlDocument)
    payload = GetPayload(xmlDocument)
    # Parse company info fields
    companyXml = payload.getElementsByTagName('company')[0]
    name = companyXml.getElementsByTagName('name')[0].childNodes[0].data
    website = companyXml.getElementsByTagName('website')[0].childNodes[0].data
    order = payload.getElementsByTagName('order')[0]
    # Parse order info
    edition = order.getElementsByTagName('editionCode')[0].childNodes[0].data
    logging.info("Read %s %s %s" % (name, website, edition))
    companySubscription = CompanySubscription()
    companySubscription.edition = edition
    companySubscription.name = name
    companySubscription.website = website

    # Parse creator info
    companySubscription.put()
    creatorXml = event.getElementsByTagName('creator')[0]
    user = CreateUser(creatorXml, companySubscription)
    user.put()
    return "<result><success>true</success><accountIdentifier>%s</accountIdentifier></result>" % companySubscription.key().id()

def ChangeOrder(xmlDocument):
    payload = GetPayload(xmlDocument)
    accountIdentifier = GetAccountIdentifier(payload)
    subscription = GetSubscription(accountIdentifier)

    if subscription == None:
        message = "Account %s not found" % accountIdentifier
        logging.error(message)
        return errorTemplate % ("ACCOUNT_NOT_FOUND", message)

    order = payload.getElementsByTagName('order')[0]
    # Parse order info
    edition = order.getElementsByTagName('editionCode')[0].childNodes[0].data
    # Update the edition code
    subscription.edition = edition
    subscription.put()
    return successMessage

def CancelOrder(xmlDocument):
    payload = GetPayload(xmlDocument)
    accountIdentifier = GetAccountIdentifier(payload)
    subscription = GetSubscription(accountIdentifier)

    if subscription == None:
        message = "Account %s not found" % accountIdentifier
        logging.error(message)
        return errorTemplate % ("ACCOUNT_NOT_FOUND", message)

    # Delete users associated with this subscription
    userQuery = GetUsers(subscription)
    for user in userQuery:
        logging.info("Removing user: %s " % user.email)
        user.delete()
    subscription.delete()
    return successMessage

def AssignUser(xmlDocument):
    payload = GetPayload(xmlDocument)
    accountIdentifier = GetAccountIdentifier(payload)
    subscription = GetSubscription(accountIdentifier)
    if subscription == None:
        message = "Account %s not found" % accountIdentifier
        logging.error(message)
        return errorTemplate % ("ACCOUNT_NOT_FOUND", message)

    userXml = payload.getElementsByTagName('user')[0]
    user = CreateUser(userXml, subscription)
    logging.info("Assigning user %s to account %s" % \
                     (user.email, accountIdentifier))
    user.put()
    return successMessage

def UnassignUser(xmlDocument):
    payload = GetPayload(xmlDocument)
    accountIdentifier = GetAccountIdentifier(payload)
    subscription = GetSubscription(accountIdentifier)
    if subscription == None:
        message = "Account %s not found" % accountIdentifier
        logging.error(message)
        return errorTemplate % ("ACCOUNT_NOT_FOUND", message)

    userXml = payload.getElementsByTagName('user')[0]
    openid = GetUserField(userXml, 'openId')
    users = GetUsers(subscription, openid)
    if users.count() == 0:
        logging.error("User not found: %s" % openid)
        return errorTemplate % ("USER_NOT_FOUND", openid)
    user = users.get()
    logging.info("Unassigning user %s from account %s" % \
                     (user.email, accountIdentifier))
    user.delete()
    return successMessage

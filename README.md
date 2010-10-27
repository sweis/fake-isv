Fake ISV
========

This is simple fake ISV that handles AppDirect events. It always returns a success on any interactive 
URL with the account identifier "fake".

The log of the last 10 events is visible at:
fake-isv.appspot.com

These events are posted to:
fake-isv.appspot.com/events?token={token}[&returnUrl={returnUrl}]

Users assigned or unassigned are visible at:
fake-isv.appspot.com/users

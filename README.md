Fake ISV
========

This is simple fake ISV that handles AppDirect events. It always returns a success on any interactive 
URL with the account identifier "fake".

The log of the last 10 events is visible at:
* http://fake-isv.appspot.com

These events are posted to:
* http://fake-isv.appspot.com/event?token={token}[&returnUrl={returnUrl}]

For example:
* http://fake-isv.appspot.com/event?token=dummyChange

Users assigned or unassigned are visible at:
* http://fake-isv.appspot.com/users

# Odoo SH

This is an **UNOFFICIAL** library to interact with Odoo hosting platform [odoo.sh](odoo.sh).
The queries were created by parsing html responses and by observing the requests/responses over the network.

This library will be, as much as possible, maintained to be up-to-date with the platform.



### Current state

Working, but all features are not supported (see usage and try it yourself).
There is currently no documentation and no package for installation.



### Goals

As developers, there may be a lot of things we want to automate. E.g.

* Retrieving database (especially, they are asynchronous, meaning you have to regularly check if the dump is ready for download)
* Get informations over the current state of the repository
* Handle notifications

### Usage

```python
odoo = OdooSh(login, password)
project = odoo.projects["myproject"]

dev_build = project.branches["dev"].builds[0]
backup = dev_build.backups[0]
backup.download("mydatabase.zip") # Immediately download the database if possible, otherwise ask to prepare a dump first

poller = mb.poller  # poller is a property that always return a function without dependencies, useful for threading.
poller()  # Blocking, this will wait until a notification is triggered
```



### Known issues

* Github may ask to re-validate the autorization

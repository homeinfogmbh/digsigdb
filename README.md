# appcmd
Digital Signage Database.

## ORM
*digsigdb* provides ORM models for
* command
* statistics
* cleanings
* tenant to tenant messages
* damage reports
* application proxies

## Usage
This library uses the *peewee* framework to implemt its ORM models. Thus you may refer to the
[original documentation](http://docs.peewee-orm.com/en/latest/ "peewee's original documentation")
on how to use the models in respect to database queries.

## Dependencies
* [*peewee*](https://github.com/coleifer/peewee "peewee is a small, expressive ORM")
* [*configparserplus*](configparserplus "Extended config file parser")
* [*peeweeplus*](peeweeplus "Practical extensions for @coleifer's small, expressive ORM")
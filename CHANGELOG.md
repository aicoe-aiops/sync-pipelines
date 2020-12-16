# Changelog for Sync Pipelines GitHub Project

## [2.0.0] - 2020-Jul-06 - tumido

### Added

- Rebased on top of [Thoth Station - Template Project](https://github.com/thoth-station/template-project).
- Squashed `dh-argo-workflows` codebase.

## Release 3.0.0 (2020-09-17T16:15:11)
### Features
* Allow section names without underscores
* Change default config location to a mountable dir
* Add CLI test suite
* Map solgate images to pull from quay.io
* Downgrade s3fs to 0.4
* Update .aicoe-ci.yaml
* Allow for build and publish via AICoE-CI
* Add manifests
* Test suite for lookup
* Tests for utils/io [de]serialize
* Add utils S3 test suite
* Move fixtures to conftest
* Add transfer test suite
* Fix keyformatter default attributes overwrite
* Re-add support for multiple file transfer
* Add testsuite for email reports
* Move fixture_dir fixture to conftest
* Rework the email report notifications
* :truck: aicoe-ci config file, to custom ci feature requirement
* Set pipenv to not install prereleases
* Add test suite for the config parsing.
* Parse generic section of config file properly
* Add testsuite for key formatter
* Update readme to fit Solgate
* Add Twine to dev packages
* Rename Solgate
* Rewrite the key formatter
* Use click as a CLI instead of ifmain
* Use a config file instead of environment variables, support repartitioning
* Allow for unpacking in S3Fs open
* Comply with linters
* Fully adopt the Thoth's Template project
* Merge sync-pipelines original codebase
### Improvements
* Add sample config test fixture
* Allow for dynamic repartitioning and retire transfer-restructure script.
* Make S3Fs copy more clever
### Other
* Remove dead code from key formatter
### Automatic Updates
* :pushpin: Automatic update of dependency moto from 1.3.14 to 1.3.16 (#26)
* :pushpin: Automatic update of dependency pytest-mock from 3.2.0 to 3.3.1 (#25)
* :pushpin: Automatic update of dependency s3fs from 0.4.2 to 0.5.1 (#24)
* :pushpin: Automatic update of dependency pytest-cov from 2.10.0 to 2.10.1
* :pushpin: Automatic update of dependency jinja2 from 2.11.2 to 3.0.0a1

## Release 3.0.1 (2020-09-18T05:13:35)
### Features
* :books: set description content type in setup.py
### Non-functional
* :ship: enable py3.8 based pull request check

## Release 3.1.0 (2020-10-13T12:07:18)
### Features
* Use PV for data exchange and fetch argo server role on the fly
* Fix transfer logic - look for 'relpath' key instead of 'key'
* Use custom 'latest' tag as an additional push target
* Fix deserialization of Argo failures
### Automatic Updates
* :pushpin: Automatic update of dependency pytest from 6.0.2 to 6.1.1 (#46)
* :pushpin: Automatic update of dependency pytest from 6.0.2 to 6.1.1 (#45)
* :pushpin: Automatic update of dependency mypy from 0.782 to 0.790 (#44)
* :pushpin: Automatic update of dependency mypy from 0.782 to 0.790 (#43)

## Release 3.2.0 (2020-12-16T15:01:49)
### Features
* :arrow_up: Automatic update of dependencies by kebechet.
* Adjust manifests to yaml config files
* Change config format to yaml and allow for external credential files
* Bump cryptography from 3.1.1 to 3.2
* Update solgate-report documentation
* Add option to specify alert from/to/smtp via cli args or env variables
* Fix s/key/relpath/ in a testcase
### Improvements
* Update documentation with example config and dev section
* Adjust test suite to the yaml config
### Automatic Updates
* :pushpin: Automatic update of dependency pytest from 6.1.1 to 6.1.2 (#51)

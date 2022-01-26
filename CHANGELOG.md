# Changelog for Sync Pipelines GitHub Project

## Release 3.5.4 (2022-01-26T13:13:18)
* Add accorvin as a maintainer
* Update copy function to use boto3
* feat: Update USIR creds
* fix(test): Update test suite for #119
* fix: Retry on failures
* chore: Report Tower analytics to datahub not to tumido
* Fix sops metadata for floorist file
* Reschedule floorist to run only once a day for now
* Adjust floorist timedelta to 24 hours for failsafe
* Add encrypted version
* Add accorvin to OWNERS file
* Add floorist sync pipeline

## Release 3.5.3 (2021-11-01T14:47:31)
* feat: Set generous read timeout
* fix: Total transfered objects count
* :arrow_up: Automatic update of dependencies by Kebechet for the ubi8 environment
* feat: Set Koku pipeline to split on 150 files
* :arrow_up: Automatic update of dependencies by Kebechet for the ubi8 environment
* :arrow_up: Automatic update of dependencies by Kebechet
* feat: Add template folder and documentation
* Add the secret config for cost management sync pipeline
* :arrow_up: Automatic update of dependencies by Kebechet for the ubi8 environment
* Add sync pipeline for cost-management data
* Add sync pipeline for rhods-metrics
* :arrow_up: Automatic update of dependencies by Kebechet
* :arrow_up: Automatic update of dependencies by Kebechet
* feat(manifets): Split file list to partials to parallelize sync
* :arrow_up: Automatic update of dependencies by Kebechet

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

## Release 3.3.0 (2021-04-21T10:45:48)
### Features
* fix: Attept to flush remote FS
* :arrow_up: Automatic update of dependencies by Kebechet (#75)
* feat: Add USIR stage sync pipeline (#74)
* :arrow_up: Automatic update of dependencies by Kebechet (#73)
* Bump cryptography from 3.3.1 to 3.3.2
* :arrow_up: Automatic update of dependencies by Kebechet (#70)
* :arrow_up: Automatic update of dependencies by kebechet. (#66)
* :arrow_up: Automatic update of dependencies by kebechet.
* fix: Make MMS pipeline overlap the time constrain
* feat: Remove Argo Events usage and add prod overlays
### Bug Fixes
* feat: Enrich reporting with error codes for different failure cases

## Release 3.4.0 (2021-05-11T19:15:28)
### Features
* feat: Add a backfill flag (#86)
* :arrow_up: Automatic update of dependencies by Kebechet
* :arrow_up: Automatic update of dependencies by Kebechet (#84)
* Make S3 remote object listing dynamic via generators (#83)
* fix: Enable tower analytics sync (#81)
* :arrow_up: Automatic update of dependencies by Kebechet (#80)
* feat: Add Tower Analytics stage/prod sync pipelines (#79)

## Release 3.4.1 (2021-05-12T08:22:22)
### Features
* :arrow_up: Automatic update of dependencies by Kebechet (#96)
* :arrow_up: Automatic update of dependencies by Kebechet (#93)
* fix: Backfill param passing from workflow (#94)
* fix: Optional param in wftmpl (#92)

## Release 3.5.0 (2021-05-20T10:46:11)
### Features
* :arrow_up: Automatic update of dependencies by Kebechet (#97)
* Switch to boto3, add `--silent`, `--dry-run` and retry loginc (#99)

## Release 3.5.1 (2021-05-20T13:06:47)
### Features
* fix: List all deps in setup.py (#102)

## Release 3.5.2 (2021-05-26T16:00:50)
### Features
* fix(logging): Add logging for backfill listing (#105)

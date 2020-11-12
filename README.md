# Solgate

![License](https://img.shields.io/github/license/aicoe-aiops/sync-pipelines)
![Python version](https://img.shields.io/github/pipenv/locked/python-version/aicoe-aiops/sync-pipelines)
![Latest release](https://img.shields.io/github/v/tag/aicoe-aiops/sync-pipelines)
[![PyPI](https://img.shields.io/pypi/v/solgate)](https://pypi.org/project/solgate)
[![Quay.io](https://img.shields.io/badge/quay.io-solgate-green)](https://quay.io/repository/thoth-station/solgate)

Yet another data sync pipelines job runner.

A CLI utility that is expected to be automated via container native workflow engines like [Argo](https://argoproj.github.io/argo/) or [Tekton](https://tekton.dev/).

## Installation

```sh
pip install solgate
```

## Configuration

Solgate relies on a configuration file that holds all the information required to fully perform the synchronization. This config file is expected to be of a YAML format and it should contain following keys:

- `source` key. Value to this key specifies where the data are sourced from.
- `destinations` key. It's value is expected to be an array for locations. Their purpose is to define sync destinations.
- other top level keys for a general configuration that is not specific to a single location.

### General config section

All configuration in this section **is optional**. Use this section if you'd like to modify the default behavior. Default values are denoted below:

```yaml
alerts_smtp_server: smtp.corp.redhat.com
alerts_from: solgate-alerts@redhat.com
alerts_to: dev-null@redhat.com
timedelta: 1d
```

Description:

- `alerts_smtp_server`, `alerts_from`, `alerts_to` are used for email alerting only
- `timedelta` defines a time window in which the objects in the source bucket must have been modified, to be eligible fo the bucket listing. Only files modified no later than `timedelta` from now are included.

### Source key

```yaml
source:
  aws_access_key_id: KEY_ID
  aws_secret_access_key: SECRET
  base_path: DH-PLAYPEN/storage/input # at least the bucket name is required, sub path within this bucket is optional
  endpoint_url: https://s3.amazonaws.com # optional, defaults to s3.amazonaws.com
  formatter: "{date}/{collection}.{ext}" # optional, defaults to None
```

If the `formatter` is not set, no repartitioning is expected to happen and the S3 object key is left intact, same as it is in the source bucket (within the `base_path` context). Specifying the `formatter` in the source section only, **doesn't** result in repartitioning of all object by itself, only those destinations that also have this option specified are eligible for object key modifications.

### Destinations key

```yaml
destinations:
  - aws_access_key_id: KEY_ID
    aws_secret_access_key: SECRET
    base_path: DH-PLAYPEN/storage/output # at least the bucket name is required, sub path within this bucket is optional
    endpoint_url: https://s3.upshift.redhat.com # optional, defaults to s3.upshift.redhat.com
    formatter: "{date}/{collection}.{ext}" # optional, defaults to None
    unpack: yes # optional, defaults to False/no
```

The `endpoint_url` defaults to a different value for destination compared to source section. This is due to the usual data origin and safe destination host.

If the `formatter` is not set, no repartitioning is expected to happen and the S3 object key is left intact, same as it is in the source bucket (within the `base_path` context). If repartitioning is desired, the formatter string must be defined in the source section as well - otherwise object name can't be parsed properly from the source S3 object key.

`unpack` option specifies if the gunzipped archives should be unpacked during the transfer. The `.gz` suffix is automatically dropped from the resulting object key, no matter if the repartitioning is on or off. Switching this option on results in weaker object validation, since the implicit metadata checksum and size checks can't be used to verify the file integrity.

### Separate credentials into different files

In case you don't feel like inlining `aws_access_key_id`, `aws_secret_access_key` in plaintext into the config file is a good idea, you can separate these credentials into their distict files. If the credentials keys are not found (inlined) in the config, solgate tries to locate them in the config folder (the same folder as the main config file is located).

The credentials file is expected to contain following:

```yaml
aws_access_key_id: KEY_ID
aws_secret_access_key: SECRET
```

For source the expected filename is `source.creds.yaml`, for destinations `destination.X.creds.yaml` where `X` is the index in the `destinations` list in the main config file. For destinations we allow credentials sharing, therefore if `destination.X.creds.yaml` is not located, solgate tries to load `destination.creds.yaml` (not indexed).

#### Full example

Let's have this file structure in our `/etc/solgate`:

```sh
$ tree /etc/solgate
/etc/solgate
├── config.yaml
├── destination.0.creds.yaml
├── destination.creds.yaml
└── source.creds.yaml
```

And a main config file `/etc/solgate/config.yaml` looking like this:

```yaml
source:
  base_path: DH-PLAYPEN/storage/input

destinations:
  - base_path: DH-PLAYPEN/storage/output0 # idx=0

  - base_path: DH-PLAYPEN/storage/output1 # idx=1

  - base_path: DH-PLAYPEN/storage/output2 # idx=2
    aws_access_key_id: KEY_ID
    aws_secret_access_key: SECRET
```

Solgate will use these credentials:

- For source the `source.creds.yaml` is read, because no credentials are inlined
- For destination `idx=0` the `destination.0.creds.yaml` is used, because no credentials are inlined
- For destination `idx=1` the `destination.creds.yaml` is used, because no credentials are inlined and there's no `destination.1.creds.yaml` file
- For destination `idx=2` the inlined credentials are used

The resolution priority:

| type        | priority                                                          |
| ----------- | ----------------------------------------------------------------- |
| source      | `inlined > source.creds.yaml`                                     |
| destination | `inlined > destination.INDEX.creds.yaml > destination.creds.yaml` |

### Example config file

Here's a full configuration file example, all together.

```yaml
alerts_smtp_server: smtp.corp.redhat.com
alerts_from: solgate-alerts@redhat.com
alerts_to: dev-null@redhat.com
timedelta: 1d

source:
  aws_access_key_id: KEY_ID
  aws_secret_access_key: SECRET
  endpoint_url: https://s3.upshift.redhat.com
  formatter: "{date}/{collection}.{ext}"
  base_path: DH-PLAYPEN/storage/input

destinations:
  - aws_access_key_id: KEY_ID
    aws_secret_access_key: SECRET
    endpoint_url: https://s3.upshift.redhat.com
    formatter: "{collection}/historic/{date}-{collection}.{ext}"
    base_path: DH-PLAYPEN/storage/output

  - aws_access_key_id: KEY_ID
    aws_secret_access_key: SECRET
    endpoint_url: https://s3.upshift.redhat.com
    formatter: "{collection}/latest/full_data.csv"
    base_path: DH-PLAYPEN/storage/output
    unpack: yes
```

## Usage

Solgate is mainly intended for use in automation within Argo Workflows. However it can be also used as a standalone CLI tool for manual transfers and (via extensions) for (TBD) manifest scaffold generation and (TBD) deployed instance monitoring.

### List bucket for files ready to be transferred

Before the actual sync can be run, it is required

```sh
solgate list
```

| CLI option <img width=20/> | Config file entry | Description                                                                                    |
| -------------------------- | ----------------- | ---------------------------------------------------------------------------------------------- |
| `-o`                       |                   | Output to a file instead of stdout. Creates a listing file.                                    |
|                            | `timedelta`       | Define a lookup restriction. Only files newer than this value are reported. Defaults to 1 day. |

### Sync objects

```sh
solgate send KEY
```

| CLI option <img width=20/> | Description                                                                                                                                 |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `-l`, `--listing-file`     | A listing file ingested by this command. Format is expected to be the same as `solgate list` output. If set, the `KEY` argument is ignored. |

### Notification service

Send an workflow status alert via email from Argo environment.

Command expects to be passed values matching available Argo variable format as described [here](https://github.com/argoproj/argo/blob/master/docs/variables.md#global).

```sh
solgate report
```

Options can be set either via CLI argument or via environment variable:

<!-- Img tag enforces additional width on the column, so GitHub doesn't break line on the --option after dashes.  -->
<!-- markdownlint-capture -->
<!-- markdownlint-disable  no-inline-html -->

- Options which map to Argo Workflow variables:

  | CLI option <img width=150/> | Environment variable name | Value should map to Argo workflow variable | Description                                                         |
  | --------------------------- | ------------------------- | ------------------------------------------ | ------------------------------------------------------------------- |
  | `--failures`                | `WORKFLOW_FAILURES`       | `{{workflow.failures}}`                    | JSON serialized into a string listing all the failed workflow nodes |
  | `-n`, `--name`              | `WORKFLOW_NAME`           | `{{workflow.name}}`                        | Workflow instance name.                                             |
  | `--namespace`               | `WORKFLOW_NAMESPACE`      | `{{workflow.namespace}}`                   | Project namespace where the workflow was executed.                  |
  | `-s`, `--status`            | `WORKFLOW_STATUS`         | `{{workflow.status}}`                      | Current status of the workflow execution.                           |
  | `-t`, `--timestamp`         | `WORKFLOW_TIMESTAMP`      | `{{workflow.creationTimestamp}}`           | Workflow execution timestamp.                                       |

- Options which map to config file entries. Priority order:

  ```sh
  CLI option > Environment variable > Config file entry > Default value
  ```

  | CLI option <img width=20/> | Environment variable name | Config file entry    | Description                                                            |
  | -------------------------- | ------------------------- | -------------------- | ---------------------------------------------------------------------- |
  | `--from`                   | `ALERT_SENDER`            | `alerts_from`        | Email alert sender address. Defaults to solgate-alerts@redhat.com.     |
  | `--to`                     | `ALERT_RECIPIENT`         | `alerts_to`          | Email alert recipient address. Defaults to data-hub-alerts@redhat.com. |
  | `--smtp`                   | `SMTP_SERVER`             | `alerts_smtp_server` | SMTP server URL. Defaults to smtp.corp.redhat.com.                     |

- Other:

  | CLI option | Environment variable name | Description                       |
  | ---------- | ------------------------- | --------------------------------- |
  | `--host`   | `ARGO_UI_HOST`            | Argo UI external facing hostname. |

<!-- markdownlint-restore -->

## Workflow manifests

Additionally to the `solgate` package this repository also features deployment manifests in the `manifests` folder. The current implementation of Kubernetes manifests relies on [Argo](https://argoproj.github.io/argo/), [Argo Events](https://argoproj.github.io/argo-events/) and are structured in a [Kustomize](https://kustomize.io/) format. Environments for deployment are specified in the `manifests/overlays/ENV_NAME` folder.

Each environment features multiple solgate workflow instances. Configuration `config.ini` file and selected triggers are defined in instance subfolder within the particular environment folder.

### Deploy

Environment deployments are expected to be handled via [Argo CD](https://argoproj.github.io/argo-cd/) in [AI-CoE SRE](https://github.com/AICoE/aicoe-sre/), however it can be done manually as well.

Local prerequisites:

- [Kustomize](https://kustomize.io/)
- [sops](https://github.com/mozilla/sops)
- [ksops](https://github.com/viaduct-ai/kustomize-sops)

Already deployed platform and running services:

- [Argo](https://argoproj.github.io/argo/)
- [Argo Events](https://argoproj.github.io/argo-events/)

#### Build and deploy manifests

```sh
kustomize build --enable_alpha_plugins manifests/overlays/ENV_NAME | oc apply -f -
```

### Create a new instance

**Will be handled via scaffold in next version!** <!-- noqa -->

Prerequisites:

Import GPG keys `EFDB9AFBD18936D9AB6B2EECBD2C73FF891FBC7E`, `A76372D361282028A99F9A47590B857E0288997C`, `04DAFCD9470A962A2F272984E5EB0DA32F3372AC`

```sh
gpg --keyserver keyserver.ubuntu.com --recv EFDB9AFBD18936D9AB6B2EECBD2C73FF891FBC7E A76372D361282028A99F9A47590B857E0288997C 04DAFCD9470A962A2F272984E5EB0DA32F3372AC
```

1. Create new folder named after the instance in the selected environment overlay.
2. Create a `kustomization.yaml` file in this new folder with following content:

   ```yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization

   generators:
     - ./secret-generator.yaml
   ```

3. Create a `secret-generator.yaml` file in this new folder with following content:

   ```yaml
   apiVersion: viaduct.ai/v1
   kind: ksops
   metadata:
     name: secret-generator
   files:
     - INSTANCE_NAME.enc.yaml
   ```

4. Create a `INSTANCE_NAME.enc.yaml` file in this folder and encrypt it via sops:

   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: dev-instance
   stringData:
     source.creds.yaml: |
       aws_access_key_id: KEY_ID_FOR_SOURCE
       aws_secret_access_key: SECRET_FOR_SOURCE

     destination.creds.yaml: |
       aws_access_key_id: DEFAULT_KEY_ID_FOR_DESTINATIONS
       aws_secret_access_key: DEFAULT_SECRET_FOR_DESTINATIONS

     destination.2.creds.yaml: |
       aws_access_key_id: KEY_ID_FOR_DESTINATION_ON_INDEX_2
       aws_secret_access_key: SECRET_FOR_DESTINATION_ON_INDEX_2

     config.yaml: |
       alerts_smtp_server: smtp.corp.redhat.com
       alerts_from: solgate-alerts@redhat.com
       alerts_to: dev-null@redhat.com
       timedelta: 5h

       source:
         endpoint_url: https://s3.upshift.redhat.com
         formatter: "{date}/{collection}.{ext}"
         base_path: DH-PLAYPEN/storage/input

       destinations:
         - endpoint_url: https://s3.upshift.redhat.com
           formatter: "{collection}/historic/{date}-{collection}.{ext}"
           base_path: DH-PLAYPEN/storage/output
           unpack: yes

         - endpoint_url: https://s3.upshift.redhat.com
           formatter: "{collection}/latest/full_data.csv"
           base_path: DH-PLAYPEN/storage/output
           unpack: yes

         - endpoint_url: https://s3.upshift.redhat.com
           base_path: DH-PLAYPEN/storage/output
   ```

   ```sh
   sops -e -i overlays/ENV_NAME/NEW_INSTANCE_NAME/INSTANCE_NAME.env.yaml
   ```

   Please make sure the `*.creds.yaml` entries in the secret are encrypted.

5. Create all event source patch files for this instance (`webhook-es.yaml`, `calendar-es.yaml`, etc.).
6. Update the resource and patch listing in the `overlays/ENV_NAME/kustomization.yaml`:

   ```yaml
   resources:
     - ...
     - ./NEW_INSTANCE_NAME

   patchesStrategicMerge:
     - ...
     - ./NEW_INSTANCE_NAME/EVENT_SOURCE_TYPE-es.yaml # For each event source trigger used
   ```

## Developer setup

### Local setup

Install `pipenv` and set up the environment:

```sh
pipenv sync -d
```

Install/enable [pre-commit](https://pre-commit.com/) for this project:

```sh
pip install -g pre-commit
pre-commit install
```

### Running tests

With local environment set up, you can run tests locally like this:

```sh
pipenv run pytest . --cov solgate
```

### Building manifests

Install local prerequisites for `kustomize` manifests:

- [Kustomize](https://kustomize.io/)
- [sops](https://github.com/mozilla/sops)
- [ksops](https://github.com/viaduct-ai/kustomize-sops)

Use `kustomize build --enable_aplha_plugins ...` to build manifests.

### CI/CD

We rely on [AICoE-CI](https://github.com/AICoE/aicoe-ci) GitHub application and bots to provide CI for us. All is configured via `.aicoe-ci.yaml`.

### Releasing

If you're a maintainer, please release via [GitHub issues](https://github.com/aicoe-aiops/sync-pipelines/issues/new/choose). New release creates:

- Creates a `git` [release tag](https://github.com/aicoe-aiops/sync-pipelines/releases) on GitHub.
- Pushes new image to Quay.io [thoth-station/solgate](https://quay.io/repository/thoth-station/solgate), tagged by the released version and `latest`.
- Releases to PyPI [solgate](https://pypi.org/project/solgate) project.

# Solgate

Yet another data sync pipelines job runner.

A CLI utility that is expected to be automated via container native workflow engines like [Argo](https://argoproj.github.io/argo/) or [Tekton](https://tekton.dev/).

## Installation

```sh
pip install solgate
```

## Configuration

Solgate relies on a configuration file that holds all the information required to fully perform the synchronization. This file is a standard INI/TOML file that contains following sections:

- Exactly one section starting with `source_`. This is a location specifying section where the data are sourced from.
- Multiple (at least one) sections starting with `destination_`. These are also location specifying sections. Their purpose is to define sync destinations.
- Section named `solgate` for a general configuration that is not specific to a single location.

### Section `solgate`

All configuration in this section **is optional**. Use this section if you'd like to modify the default behavior. Default values are denoted below:

```ini
[solgate]
alerts_smtp_server = smtp.corp.redhat.com
alerts_from        = solgate-alerts@redhat.com
alerts_to          = dev-null@redhat.com
timedelta          = 1d
```

Description:

- `alerts_smtp_server`, `alerts_from`, `alerts_to` are used for alerting only
- `timedelta` defines a time window in which the objects in the source bucket must have been modified, to be eligible fo the bucket listing. Only files modified no later than `timedelta` from now are included.

### Source section

```ini
[source_some_fancy_name]
aws_access_key_id     = KEY_ID
aws_secret_access_key = SECRET
base_path             = DH-PLAYPEN/storage/input   ; at least the bucket name is required, sub path within this bucket is optional
endpoint_url          = https://s3.amazonaws.com   ; optional, defaults to s3.amazonaws.com
formatter             = {date}/{collection}.{ext}  ; optional, defaults to None
```

If the `formatter` is not set, no repartitioning is expected to happen and the S3 object key is left intact, same as it is in the source bucket (within the `base_path` context). Specifying the `formatter` in the source section only, **doesn't** result in repartitioning of all object by itself, only those destinations that also have this option specified are eligible for object key modifications.

### Destination sections

```ini
[destination_some_fancy_name]
aws_access_key_id     = KEY_ID
aws_secret_access_key = SECRET
base_path             = DH-PLAYPEN/storage/output      ; at least the bucket name is required, sub path within this bucket is optional
endpoint_url          = https://s3.upshift.redhat.com  ; optional, defaults to s3.upshift.redhat.com
formatter             = {date}/{collection}.{ext}      ; optional, defaults to None
unpack                = yes                            ; optional, defaults to False/no
```

The `endpoint_url` defaults to a different value for destination compared to source section. This is due to the usual data origin and safe destination host.

If the `formatter` is not set, no repartitioning is expected to happen and the S3 object key is left intact, same as it is in the source bucket (within the `base_path` context). If repartitioning is desired, the formatter string must be defined in the source section as well - otherwise object name can't be parsed properly from the source S3 object key.

`unpack` option specifies if the gunzipped archives should be unpacked during the transfer. The `.gz` suffix is automatically dropped from the resulting object key, no matter if the repartitioning is on or off. Switching this option on results in weaker object validation, since the implicit metadata checksum and size checks can't be used to verify the file integrity.

## Usage

Solgate is mainly intended for use in automation within Argo Workflows. However it can be also used as a standalone CLI tool for manual transfers and (via extensions) for (TBD) manifest scaffold generation and (TBD) deployed instance monitoring.

### List bucket for files ready to be transferred

Before the actual sync can be run, it is required

```sh
solgate list
```

### Sync objects

```sh
solgate transfer
```

### Nofitication service

```sh
solgate notify
```

## Workflow manifests

Additionally to the `solgate` package source code this repository also features deployment manifests in the `manifests` folder. The current implementation of Kubernetes manifests relies on [Argo](https://argoproj.github.io/argo/), [Argo Events](https://argoproj.github.io/argo-events/) and are structured in a [Kustomize](https://kustomize.io/) format. Environments for deployment are specified in the `manifests/overlays/ENV_NAME` folder.

Each environment features multiple solgate workflow instances. Configuration `config.ini` file and selected triggers are defined in instance subfolder within the particular environment folder.

### Deploy

Environment deployments are expected to be handled via [Argo CD](https://argoproj.github.io/argo-cd/) in [AI-CoE SRE](https://github.com/AICoE/aicoe-sre/), however it can be done manually as well.

Local prerequisites:

- [Kustomize](https://kustomize.io/)
- [sops](https://github.com/mozilla/sops)
- [kustomize-sopssecretgenerator](https://github.com/goabout/kustomize-sopssecretgenerator)

Note: Yes, we don't use [ksops] here, instead we are currently using a different sops abstraction. It is because we would like to track as much of the configuration files is a readable format (and generate the secrets from them on the fly), opposed to ksops, which requires Kubernetes secret resources which are base64 encoded (harder to review).

Already deployed platform and running services:

- [Argo](https://argoproj.github.io/argo/)
- [Argo Events](https://argoproj.github.io/argo-events/)

#### Build and deploy manifests

```sh
kustomize build --enable_alpha_plugins manifests/overlays/ENV_NAME | oc apply -f -
```

### Create a new instance

**Will be handled via scaffold in next version!** <!-- noqa -->

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
   apiVersion: goabout.com/v1beta1
   kind: SopsSecretGenerator
   metadata:
   name: NEW_INSTANCE_NAME
   files:
     - config.ini
   ```

4. Create a `config.ini` file in this folder and encrypt it via sops:

   ```sh
   vim overlays/ENV_NAME/NEW_INSTANCE_NAME/config.ini
   sops -e -i overlays/ENV_NAME/NEW_INSTANCE_NAME/config.ini
   ```

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

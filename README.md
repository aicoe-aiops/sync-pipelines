# Argo Workflows

Data ingress pipelines for DataHub via Argo pipelines.

## Runbook

The Runbook for the Argo workflows can be found in the dh-runbooks repository at [ARGO-WORKFLOWS.md](https://gitlab.cee.redhat.com/data-hub/dh-runbooks/blob/master/ARGO-WORKFLOWS.md)

## Installation and set up

[Ansible Playbook Bundle](https://docs.openshift.com/container-platform/3.11/apb_devel/index.html) is used to deploy this repository. This is a common deployment strategy used for all the DataHub and ODH.

### Prerequisites

1. Use [pipenv](https://pipenv.readthedocs.io/en/latest/). Install pipenv by running the following command:

   ```bash
   $ pip install --user pipenv
   ...

   $ pipenv sync --dev
   Creating a virtualenv for this project…
   ...

   $ pipenv shell
   Launching subshell in virtual environment…
   ...
   ```

2. Use `oc` to provide Ansible Playbook Bundle with proper cluster connection. (TIP: It's useful to set up a OpenShift context for each cluster so you can switch different clusters and environments):

   ```sh
   oc config set-cluster datahub --server https://datahub.psi.redhat.com:443
   oc config set-credentials datahub --token=<YOUR USER TOKEN>
   oc config set-context datahub --cluster=datahub --user=datahub
   ```

   Ansible Playbook Bundle orchestration will reuse the current `oc` credentials. It also expects the target namespace to exist.

### Deploy ODH Operator

Follow the steps in this repo to deploy the ODH Operator: [dh-internal-odh-install](https://gitlab.cee.redhat.com/data-hub/dh-internal-odh-install)

### Deploy Argo

Follow the steps in this repo to deploy Argo and Argo events: [dh-argo](https://gitlab.cee.redhat.com/data-hub/dh-argo)

## Deploy the workflows

This repository currently supports `prod`, `stage` and `dev` environments, custom environments are described in the [next section](#set-up-custom-environment).

To deploy the environment execute within your `pipenv` virtual environment:

```bash
$ ansible-playbook playbook.yaml \
    --ask-vault-pass
    -e kubeconfig=$HOME/.kube/config \
    -e target_env=prod
```

If you'd like to check what OpenShift entities are generated via the playbook, if may be usefull to run the previous command with additional `--check` and `-vvv` arguments.

## Available roles

### Tools

Lives in `roles/tools`. Hosts all utilities that sync-pipeline needs. It is built on top of S2I Python container and can be managed as a standalone resource with separate dependency resolution using nested Pipenv environment. It also contains a `WorkflowTemplate` that utilizes included tools and scripts for easier import into other workflows.

### Sync Pipeline

Linear workflow for S3 bucket synchronization:

1. Check if new data are present in the source bucket.
2. Sync the new content to destination bucket.
3. Verify if the sync created new data in destination bucket.

To define a new sync pipeline instance, simply update `sync_pipelines` key in your environment file in `vars` folder with:

```yml
sync_pipelines:
  <PIPELINE_NAME>:
    source: <SECRET_NAME> # Required
    destination: <SECRET_NAME_OR_LIST> # Required
    # Note: For all optional paramaters the default value is taken from root of the environment file. If not set there - from roles/sync-pipeline/defaults/main.yml
    schedule: <CRON_STRING> # Optional
    timedelta: <SYNCHRONIZED_DATA_WINDOW> # Optional
    transfer_strategy: via-restructure # Optional
    alerts_smtp_server: <SMTP_SERVER> # Optional
    alerts_to: <LIST_OF_RECIPIENT_EMAIL_ADDRESSES> # Optional
    alerts_from: <ALERT_SENDER_EMAIL_ADDRESS> # Optional
```

A pipeline definition specifies from which secret (`source`) to which other secret (`destination`) to sync the data. If the desired behavior is to sync the source data to multiple locations, you can list all the destinations as a list:

```yml
sync_pipelines:
  pipeline-with-single-destination:
    destination: destination_secret-name
    ...
  pipeline-with-multiple-destinations:
    destination:
      - first-destination-secret-name
      - second-destination-secret-name
```

Both destinations will be synchronized from the `source` in paralel in the same workflow run.

Secret name used as a value in `source` and `destination` fields, require corresponding entry in the [Secrets] section of the environment file.

Using custom transfer strategy is possible via the `transfer_strategy` switch mentioned above. This allows you to select which transfer step in the workflow will be used. Currently supported strategies are:

1. `default` - executes a MinIO client and performs `mc mirror` operation.
2. `via-restructure` - executes custom `restructure.py` stript from `tools` image.

All these pipeline config variables can be overwrite any top level context or default variable, see [Variable precedence](#variable-precedence).

## Set up custom environment

Target environment is set up via top level variables definition. To set up your own environment, just create a file in `./vars` folder named as `<ENV_NAME>-env.yml`.

### Environment file structure

```yml
namespace: <OPENSHIFT_PROJECT_NAMESPACE>

sync-pipelines: ... # Dict of deployed sync pipelines

secrets: ... # Dict of all deployed secrets
```

### Secrets

Synchronization pipelines use secrets to define the data source and destination. To allow that behavior, you have to specify the secrets in the environment file in a designated `secrets` section:

```yml
secrets:
  <SECRET_NAME>:
    url: <URL>
    path: <INPUT_PATH>
    access_key: <SECRET>
    access_key_id: <KEY>
  ...
```

### Other available variables and settings

You can override any default variable value. These are the available properties, that can be set:

```yml
# For tools
source_repository_uri: <TOOLS_SOURCE_REPO_URL>
source_repository_ref: <TOOLS_REPO_REF>

schedule: <CRON_SCHEDULE>
timedelta: <TIME_WINDOW_TO_CHECK>

# For email alerting
alerts_smtp_server: <SMTP_SERVER>
alerts_to: <LIST_OF_RECIPIENT_EMAIL_ADDRESSES>
alerts_from: <ALERT_SENDER_EMAIL_ADDRESS>
```

### Variable precedence

[Ansible docs](https://docs.ansible.com/ansible/latest/user_guide/playbooks_variables.html#variable-precedence-where-should-i-put-a-variable) specifies variable precedence. In our case this means (sorted from the most prioritized to the least):

1. Variables defined in `/vars/<ENV>-env.yml` in `sync-pipelines/<PIPELINE_NAME>` scope
2. Variables defined in `/vars/<ENV>-env.yml` in top level
3. Role defaults in `role/<ROLE_NAME>/defaults/<ANY_NAME>.yml`

If still in doubt see [this test](https://gist.github.com/tumido/67688bce3471c9023128492f525e31c8).

## Resources

To learn more about this orchestration strategy, please visit:

- Ansible Playbook Bundle:
  - [OpenShift guides](https://docs.openshift.com/container-platform/3.11/apb_devel/index.html)
  - [Github](https://github.com/automationbroker/apb)
- Ansible [K8s module](https://docs.ansible.com/ansible/latest/modules/k8s_module.html#k8s-raw-module)
- [Argo pipeline definition](https://argoproj.github.io/docs/argo/examples/readme.html)

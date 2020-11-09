#   Copyright 2020 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#
import logging
import os
import json
import yaml

from validations_libs.ansible import Ansible as v_ansible
from validations_libs.group import Group
from validations_libs.validation_logs import ValidationLogs, ValidationLog
from validations_libs import constants
from validations_libs import utils as v_utils

LOG = logging.getLogger(__name__ + ".validation_actions")


class ValidationActions(object):

    def __init__(self, validation_path=None, group=None):
        self.log = logging.getLogger(__name__ + ".ValidationActions")
        self.validation_path = (validation_path if validation_path
                                else constants.ANSIBLE_VALIDATION_DIR)
        self.group = group

    def list_validations(self):
        """List the available validations"""
        self.log = logging.getLogger(__name__ + ".list_validations")
        validations = v_utils.parse_all_validations_on_disk(
            self.validation_path, self.group)

        return_values = []
        column_name = ('ID', 'Name', 'Groups')

        for val in validations:
            return_values.append((val.get('id'), val.get('name'),
                                  val.get('groups')))
        return (column_name, return_values)

    def show_validations(self, validation,
                         log_path=constants.VALIDATIONS_LOG_BASEDIR):
        """Display detailed information about a Validation"""
        self.log = logging.getLogger(__name__ + ".show_validations")
        # Get validation data:
        vlog = ValidationLogs(log_path)
        data = v_utils.get_validations_data(validation, self.validation_path)
        if not data:
            msg = "Validation {} not found in the path: {}".format(
                validation,
                self.validation_path)
            raise RuntimeError(msg)
        logfiles = vlog.get_logfile_content_by_validation(validation)
        format = vlog.get_validations_stats(logfiles)
        data.update(format)
        return data

    def run_validations(self, validation_name=None, inventory='localhost',
                        group=None, extra_vars=None, validations_dir=None,
                        extra_env_vars=None, ansible_cfg=None, quiet=True,
                        workdir=None, limit_hosts=None, run_async=False,
                        base_dir=constants.DEFAULT_VALIDATIONS_BASEDIR,
                        log_path=None, python_interpreter=None):
        self.log = logging.getLogger(__name__ + ".run_validations")
        playbooks = []
        validations_dir = (validations_dir if validations_dir
                           else self.validation_path)
        if group:
            self.log.debug('Getting the validations list by group')
            try:
                validations = v_utils.parse_all_validations_on_disk(
                    validations_dir, group)
                for val in validations:
                    playbooks.append(val.get('id') + '.yaml')
            except Exception as e:
                raise(e)
        elif validation_name:
            validation_name = v_utils.convert_data(validation_name)

            playbooks = v_utils.get_validations_playbook(validations_dir,
                                                         validation_name,
                                                         group)

            if not playbooks or len(validation_name) != len(playbooks):
                p = []
                for play in playbooks:
                    p.append(os.path.basename(os.path.splitext(play)[0]))

                unknown_validation = list(set(validation_name) - set(p))

                msg = "Validation {} not found in {}.".format(
                    unknown_validation, validations_dir)

                raise RuntimeError(msg)
        else:
            raise RuntimeError("No validations found")

        self.log.debug('Running the validations with Ansible')
        results = []
        for playbook in playbooks:
            validation_uuid, artifacts_dir = v_utils.create_artifacts_dir(
                prefix=os.path.basename(playbook))
            run_ansible = v_ansible(validation_uuid)
            _playbook, _rc, _status = run_ansible.run(
                workdir=artifacts_dir,
                playbook=playbook,
                base_dir=base_dir,
                playbook_dir=validations_dir,
                parallel_run=True,
                inventory=inventory,
                output_callback='validation_json',
                quiet=quiet,
                extra_vars=extra_vars,
                limit_hosts=limit_hosts,
                extra_env_variables=extra_env_vars,
                ansible_cfg=ansible_cfg,
                gathering_policy='explicit',
                ansible_artifact_path=artifacts_dir,
                log_path=log_path,
                run_async=run_async,
                python_interpreter=python_interpreter)
            results.append({'playbook': _playbook,
                            'rc_code': _rc,
                            'status': _status,
                            'validations': _playbook.split('.')[0],
                            'UUID': validation_uuid,
                            })
        if run_async:
            return results
        # Return log results
        uuid = [id['UUID'] for id in results]
        vlog = ValidationLogs()
        return vlog.get_results(uuid)

    def group_information(self, groups):
        """Get Information about Validation Groups"""
        val_gp = Group(groups)
        group = val_gp.get_formated_group

        group_info = []
        # Get validations number by groups
        for gp in group:
            validations = v_utils.parse_all_validations_on_disk(
                self.validation_path, gp[0])
            group_info.append((gp[0], gp[1], len(validations)))
        column_name = ("Groups", "Description", "Number of Validations")
        return (column_name, group_info)

    def show_validations_parameters(self, validation=None, group=None,
                                    format='json', download_file=None):
        """
        Return Validations Parameters for one or several validations by their
        names or their groups.

        :param validation: List of validation name(s)
        :type validation: `list`

        :param group: List of validation group(s)
        :type group: `list`

        :param format: Output format (Supported format are JSON or YAML)
        :type format: `string`

        :param download_file: Path of a file in which the parameters will be
                              stored
        :type download_file: `string`

        :return: A JSON or a YAML dump (By default, JSON).
                 if `download_file` is used, a file containing only the
                 parameters will be created in the file system.
        :exemple:

        >>> validation = ['check-cpu', 'check-ram']
        >>> group = None
        >>> format = 'json'
        >>> show_validations_parameters(validation, group, format)
        {
            "check-cpu": {
                "parameters": {
                    "minimal_cpu_count": 8
                }
            },
            "check-ram": {
                "parameters": {
                    "minimal_ram_gb": 24
                }
            }
        }
        """
        if not validation:
            validation = []

        if not group:
            group = []

        supported_format = ['json', 'yaml']

        if format not in supported_format:
            raise RuntimeError("{} format not supported".format(format))

        validations = v_utils.get_validations_playbook(
            self.validation_path, validation, group)
        params = v_utils.get_validations_parameters(validations, validation,
                                                    group)
        if download_file:
            params_only = {}
            with open(download_file, 'w') as f:
                for val_name in params.keys():
                    for k, v in params[val_name].get('parameters').items():
                        params_only[k] = v

                if format == 'json':
                    f.write(json.dumps(params_only,
                                       indent=4,
                                       sort_keys=True))
                else:
                    f.write(yaml.safe_dump(params_only,
                                           allow_unicode=True,
                                           default_flow_style=False,
                                           indent=2))
        if format == 'json':
            return json.dumps(params,
                              indent=4,
                              sort_keys=True)
        else:
            return yaml.safe_dump(params,
                                  allow_unicode=True,
                                  default_flow_style=False,
                                  indent=2)

    def show_history(self, validation_id=None, extension='json',
                     log_path=constants.VALIDATIONS_LOG_BASEDIR):
        """Return validations history"""
        vlogs = ValidationLogs(log_path)
        logs = (vlogs.get_logfile_by_validation(validation_id)
                if validation_id else vlogs.get_all_logfiles(extension))

        values = []
        column_name = ('UUID', 'Validations',
                       'Status', 'Execution at',
                       'Duration')
        for log in logs:
            vlog = ValidationLog(logfile=log)
            if vlog.is_valid_format():
                for play in vlog.get_plays:
                    values.append((play['id'], play['validation_id'],
                                   vlog.get_status,
                                   play['duration'].get('start'),
                                   play['duration'].get('time_elapsed')))
        return (column_name, values)

    def get_status(self, validation_id=None, uuid=None, status='FAILED',
                   log_path=constants.VALIDATIONS_LOG_BASEDIR):
        """Return validations execution details by status"""
        vlogs = ValidationLogs(log_path)
        if validation_id:
            logs = vlogs.get_logfile_by_validation(validation_id)
        elif uuid:
            logs = vlogs.get_logfile_by_uuid(uuid)
        else:
            raise RuntimeError("You need to provide a validation_id or a uuid")

        values = []
        column_name = ['name', 'host', 'status', 'task_data']
        for log in logs:
            vlog = ValidationLog(logfile=log)
            if vlog.is_valid_format():
                for task in vlog.get_tasks_data:
                    if task['status'] == status:
                        for host in task['hosts']:
                            values.append((task['name'], host, task['status'],
                                           task['hosts'][host]))
        return (column_name, values)

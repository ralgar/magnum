# Copyright 2015 Rackspace  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import contextlib

import docker
from docker.utils import utils
from oslo_config import cfg

from magnum.common import utils as magnum_utils
from magnum.conductor.handlers.common import cert_manager
from magnum.conductor.handlers.common import docker_client
from magnum.conductor import utils as conductor_utils
from magnum import objects


docker_opts = [
    cfg.StrOpt('docker_remote_api_version',
               default=docker_client.DEFAULT_DOCKER_REMOTE_API_VERSION,
               help='Docker remote api version. Override it according to '
                    'specific docker api version in your environment.'),
    cfg.IntOpt('default_timeout',
               default=docker_client.DEFAULT_DOCKER_TIMEOUT,
               help='Default timeout in seconds for docker client '
                    'operations.'),
    cfg.BoolOpt('api_insecure',
                default=False,
                help='If set, ignore any SSL validation issues'),
    cfg.StrOpt('ca_file',
               help='Location of CA certificates file for '
                    'securing docker api requests (tlscacert).'),
    cfg.StrOpt('cert_file',
               help='Location of TLS certificate file for '
                    'securing docker api requests (tlscert).'),
    cfg.StrOpt('key_file',
               help='Location of TLS private key file for '
                    'securing docker api requests (tlskey).'),
]
CONF = cfg.CONF
CONF.register_opts(docker_opts, 'docker')


def parse_docker_image(image):
    image_parts = image.split(':', 1)

    image_repo = image_parts[0]
    image_tag = None

    if len(image_parts) > 1:
        image_tag = image_parts[1]

    return image_repo, image_tag


def is_docker_library_version_atleast(version):
    if utils.compare_version(docker.version, version) <= 0:
        return True
    return False


@contextlib.contextmanager
def docker_for_container(context, container):
    if magnum_utils.is_uuid_like(container):
        container = objects.Container.get_by_uuid(context, container)
    bay = conductor_utils.retrieve_bay(context, container.bay_uuid)
    with docker_for_bay(context, bay) as docker:
        yield docker


@contextlib.contextmanager
def docker_for_bay(context, bay):
    baymodel = conductor_utils.retrieve_baymodel(context, bay)

    ca_cert, magnum_key, magnum_cert = None, None, None
    client_kwargs = dict()
    if not baymodel.tls_disabled:
        (ca_cert, magnum_key,
         magnum_cert) = cert_manager.create_client_files(bay)
        client_kwargs['ca_cert'] = ca_cert.name
        client_kwargs['client_key'] = magnum_key.name
        client_kwargs['client_cert'] = magnum_cert.name

    yield docker_client.DockerHTTPClient(
        bay.api_address,
        CONF.docker.docker_remote_api_version,
        CONF.docker.default_timeout,
        **client_kwargs
    )

    if ca_cert:
        ca_cert.close()
    if magnum_key:
        magnum_key.close()
    if magnum_cert:
        magnum_cert.close()

from __future__ import annotations

import cgi
import json
import logging
from typing import Any, Optional, Union

from werkzeug.wrappers.response import Response as WerkzeugResponse
import flask
from flask.views import MethodView

import ckan.lib.base as base
import ckan.lib.datapreview as lib_datapreview
from ckan.lib.helpers import helper_functions as h
import ckan.lib.navl.dictization_functions as dict_fns
import ckan.lib.uploader as uploader
import ckan.logic as logic
import ckan.model as model
import ckan.plugins as plugins
from ckan.lib import signals
from ckan.common import _, config, g, request, current_user
from ckan.views.home import CACHE_PARAMETERS
from ckan.views.dataset import (
    _get_pkg_template, _get_package_type, _setup_template_variables
)

from ckan.types import Context, Response

Blueprint = flask.Blueprint
NotFound = logic.NotFound
NotAuthorized = logic.NotAuthorized
ValidationError = logic.ValidationError
check_access = logic.check_access
get_action = logic.get_action
tuplize_dict = logic.tuplize_dict
clean_dict = logic.clean_dict
parse_params = logic.parse_params
flatten_to_string_key = logic.flatten_to_string_key

log = logging.getLogger(__name__)

# encoding: utf-8
import os
import logging
import mimetypes

import cgi
import json
import logging
from typing import Any, Optional, Union

from werkzeug.wrappers.response import Response as WerkzeugResponse
import flask
from flask.views import MethodView

import ckan.lib.base as base
import ckan.lib.datapreview as lib_datapreview
from ckan.lib.helpers import helper_functions as h
import ckan.lib.navl.dictization_functions as dict_fns
import ckan.lib.uploader as uploader
import ckan.logic as logic
import ckan.model as model
import ckan.plugins as plugins
from ckan.lib import signals
from ckan.common import _, config, g, request, current_user
from ckan.views.home import CACHE_PARAMETERS
from ckan.views.dataset import (
    _get_pkg_template, _get_package_type, _setup_template_variables
)

from ckan.types import Context, Response

Blueprint = flask.Blueprint
NotFound = logic.NotFound
NotAuthorized = logic.NotAuthorized
ValidationError = logic.ValidationError
check_access = logic.check_access
get_action = logic.get_action
tuplize_dict = logic.tuplize_dict
clean_dict = logic.clean_dict
parse_params = logic.parse_params
flatten_to_string_key = logic.flatten_to_string_key

log = logging.getLogger(__name__)
import flask

from botocore.exceptions import ClientError

from ckantoolkit import config as ckan_config
from ckantoolkit import _, request, c, g
import ckantoolkit as toolkit
import ckan.logic as logic
import ckan.lib.base as base
import ckan.lib.uploader as uploader
from ckan.lib.uploader import get_storage_path

import ckan.model as model

log = logging.getLogger(__name__)

Blueprint = flask.Blueprint
NotFound = logic.NotFound
NotAuthorized = logic.NotAuthorized
get_action = logic.get_action
abort = base.abort
redirect = toolkit.redirect_to


s3_resource = Blueprint(
    u's3_resource',
    __name__,
    url_prefix=u'/dataset/<id>/resource',
    url_defaults={u'package_type': u'dataset'}
)


def resource_download(package_type, id, resource_id, filename=None):
    '''
    Provide a download by either redirecting the user to the url stored or
    downloading the uploaded file from S3.
    '''
    context = {'model': model, 'session': model.Session,
               'user': c.user or c.author, 'auth_user_obj': c.userobj}

    try:
        rsc = get_action('resource_show')(context, {'id': resource_id})
        get_action('package_show')(context, {'id': id})
    except NotFound:
        return abort(404, _('Resource not found'))
    except NotAuthorized:
        return abort(401, _('Unauthorized to read resource %s') % id)

    if rsc.get('url_type') == 'upload':

        upload = uploader.get_resource_uploader(rsc)
        preview = request.args.get(u'preview', False)

        if filename is None:
            filename = os.path.basename(rsc['url'])
        key_path = upload.get_path(rsc['id'], filename)
        key = filename

        if key is None:
            log.warn('Key \'{0}\' not found in bucket \'{1}\''
                     .format(key_path, upload.bucket_name))

        try:
            if preview:
                url = upload.get_signed_url_to_key(key_path)
            else:
                params = {
                    'ResponseContentDisposition':
                        'attachment; filename=' + filename,
                }
                url = upload.get_signed_url_to_key(
                    key_path, params, read_only=True)
            return redirect(url)

        except ClientError as ex:
            if ex.response['Error']['Code'] in ['NoSuchKey', '404']:
                # attempt fallback
                if ckan_config.get(
                        'ckanext.s3filestore.filesystem_download_fallback',
                        False):
                    log.info('Attempting filesystem fallback for resource {0}'
                             .format(resource_id))
                    url = toolkit.url_for(
                        u's3_resource.filesystem_resource_download',
                        id=id,
                        resource_id=resource_id,
                        filename=filename,
                        preview=preview)
                    return redirect(url)

                return abort(404, _('Resource data not found'))
            else:
                raise ex
    else:
        return redirect(rsc[u'url'])


def filesystem_resource_download(package_type, id, resource_id, filename=None):
    """
    A fallback view action to download resources from the
    filesystem. A copy of the action from
    `ckan.views.resource:download`.

    Provides a direct download by either redirecting the user to the url
    stored or downloading an uploaded file directly.
    """
    context = {
        u'model': model,
        u'session': model.Session,
        u'user': g.user,
        u'auth_user_obj': g.userobj
    }
    preview = request.args.get(u'preview', False)

    try:
        rsc = get_action(u'resource_show')(context, {u'id': resource_id})
        get_action(u'package_show')(context, {u'id': id})
    except (NotFound, NotAuthorized):
        return abort(404, _(u'Resource not found'))

    mimetype, enc = mimetypes.guess_type(
        rsc.get('url', ''))

    if rsc.get(u'url_type') == u'upload':
        path = get_storage_path()
        storage_path = os.path.join(path, 'resources')
        directory = os.path.join(storage_path,
                                 resource_id[0:3], resource_id[3:6])
        filepath = os.path.join(directory, resource_id[6:])
        if preview:
            return flask.send_file(filepath, mimetype=mimetype)
        else:
            return flask.send_file(filepath)
    elif u'url' not in rsc:
        return abort(404, _(u'No download is available'))
    return redirect(rsc[u'url'])


s3_resource.add_url_rule(u'/<resource_id>/download',
                         view_func=resource_download)
s3_resource.add_url_rule(u'/<resource_id>/download/<filename>',
                         view_func=resource_download)
s3_resource.add_url_rule(u'/<resource_id>/fs_download/<filename>',
                         view_func=filesystem_resource_download)


def get_blueprints():
    return [s3_resource, resource, prefixed_resource]

resource = Blueprint(
    u'dataset_resource1',
    __name__,
    url_prefix=u'/dataset/<id>/resource',
    url_defaults={u'package_type': u'dataset'}
)
prefixed_resource = Blueprint(
    u'resource1',
    __name__,
    url_prefix=u'/dataset/<id>/resource',
    url_defaults={u'package_type': u'dataset'}
)

class CreateView(MethodView):
    def post(self, package_type: str, id: str) -> Union[str, Response]:
        save_action = request.form.get(u'save')
        data = clean_dict(
            dict_fns.unflatten(tuplize_dict(parse_params(request.form)))
        )
        data.update(clean_dict(
            dict_fns.unflatten(tuplize_dict(parse_params(request.files)))
        ))

        # we don't want to include save as it is part of the form
        del data[u'save']
        resource_id = data.pop(u'id')

        context: Context = {
            u'user': current_user.name,
            u'auth_user_obj': current_user
        }

        # see if we have any data that we are trying to save
        data_provided = False
        for key, value in data.items():
            if (
                    (value or isinstance(value, cgi.FieldStorage))
                    and key != u'resource_type'):
                data_provided = True
                break

        if not data_provided and save_action != u"go-dataset-complete":
            if save_action == u'go-dataset':
                # go to final stage of adddataset
                return h.redirect_to(u'{}.edit'.format(package_type), id=id)
            # see if we have added any resources
            try:
                data_dict = get_action(u'package_show')(context, {u'id': id})
            except NotAuthorized:
                return base.abort(403, _(u'Unauthorized to update dataset'))
            except NotFound:
                return base.abort(
                    404,
                    _(u'The dataset {id} could not be found.').format(id=id)
                )
            if not len(data_dict[u'resources']):
                # no data so keep on page
                msg = _(u'You must add at least one data resource')
                # On new templates do not use flash message

                errors: dict[str, Any] = {}
                error_summary = {_(u'Error'): msg}
                return self.get(package_type, id, data, errors, error_summary)

            # XXX race condition if another user edits/deletes
            data_dict = get_action(u'package_show')(context, {u'id': id})
            get_action(u'package_update')(
                Context(context, allow_state_change=True),
                dict(data_dict, state=u'active')
            )
            return h.redirect_to(u'{}.read'.format(package_type), id=id)

        data[u'package_id'] = id
        try:
            resource_found = False
            if resource_id:
                data[u'id'] = resource_id
                try: 
                    get_action('resource_show')(context, {'id': resource_id}).get('success')
                    resource_found = True
                except:
                    pass

            if resource_id and resource_found:
                get_action(u'resource_update')(context, data)
            else:
                get_action(u'resource_create')(context, data)
        except ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary
            if data.get(u'url_type') == u'upload' and data.get(u'url'):
                data[u'url'] = u''
                data[u'url_type'] = u''
                data[u'previous_upload'] = True
            return self.get(package_type, id, data, errors, error_summary)
        except NotAuthorized:
            return base.abort(403, _(u'Unauthorized to create a resource'))
        except NotFound:
            log.info('BROKE HERE')
            return base.abort(
                404, _(u'The resource {id} could not be found.').format(id=resource_id)
            )
        if save_action == u'go-metadata':
            # XXX race condition if another user edits/deletes
            data_dict = get_action(u'package_show')(context, {u'id': id})
            get_action(u'package_update')(
                Context(context, allow_state_change=True),
                dict(data_dict, state=u'active')
            )
            return h.redirect_to(u'{}.read'.format(package_type), id=id)
        elif save_action == u'go-dataset':
            # go to first stage of add dataset
            return h.redirect_to(u'{}.edit'.format(package_type), id=id)
        elif save_action == u'go-dataset-complete':

            return h.redirect_to(u'{}.read'.format(package_type), id=id)
        else:
            # add more resources
            return h.redirect_to(
                u'{}_resource.new'.format(package_type),
                id=id
            )

def register_dataset_plugin_rules(blueprint) -> None:
    blueprint.add_url_rule(u'/new', view_func=CreateView.as_view(str(u'new')))

register_dataset_plugin_rules(resource)
register_dataset_plugin_rules(prefixed_resource)
# remove this when we improve blueprint registration to be explicit:
resource.auto_register = False  # type: ignore
prefixed_resource.auto_register = False  # type: ignore

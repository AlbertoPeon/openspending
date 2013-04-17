import logging

from pylons import request, response, tmpl_context as c
from pylons.controllers.util import redirect
from paste.deploy.converters import asbool
from pylons.i18n import _
from colander import Invalid

from openspending import model
from openspending.model import Source, meta as db
from openspending.lib.jsonexport import to_jsonp
from openspending.ui.lib import helpers as h
from openspending.ui.lib.base import BaseController, render
from openspending.ui.lib.base import abort, require
from openspending.tasks import analyze_source, load_source
from openspending.ui.alttemplates import templating

from openspending.ui.validation.source import source_schema

log = logging.getLogger(__name__)

class SourceController(BaseController):

    def new(self, dataset, errors={}):
        self._get_dataset(dataset)
        require.dataset.update(c.dataset)
        return templating.render('source/new.html', form_errors=errors,
                form_fill=request.params if errors else None)

    def create(self, dataset):
        self._get_dataset(dataset)
        require.dataset.update(c.dataset)
        try:
            schema = source_schema()
            data = schema.deserialize(request.params)
            source = Source(c.dataset, c.account, data['url'])
            db.session.add(source)
            db.session.commit()
            analyze_source.apply_async(args=[source.id], countdown=2)
            h.flash_success(_("The source has been created."))
            redirect(h.url_for(controller='editor', action='index', 
                               dataset=c.dataset.name))
        except Invalid, i:
            errors = i.asdict()
            errors = [(k[len('source.'):], v) for k, v \
                    in errors.items()]
            return self.new(dataset, dict(errors))

    def index(self, dataset, format='json'):
        self._get_dataset(dataset)
        return to_jsonp([src.as_dict() for src in c.dataset.sources])
    
    def _get_source(self, dataset, id):
        self._get_dataset(dataset)
        c.source = Source.by_id(id)
        if c.source is None or c.source.dataset != c.dataset:
            abort(404, _("There is no source '%s'") % id)

    def view(self, dataset, id):
        self._get_source(dataset, id)
        redirect(c.source.url)

    def load(self, dataset, id):
        self._get_source(dataset, id)
        require.dataset.update(c.dataset)
        try:
            sample = asbool(request.params.get('sample', 'false'))
            load_source.delay(c.source.id, sample)
        except Exception, e:
            abort(400, e)

        h.flash_success(_("Now loading..."))
        redirect(h.url_for(controller='editor', action='index', 
                           dataset=c.dataset.name))

    def analysis(self, dataset, source, format='json'):
        self._get_source(dataset, source)
        return to_jsonp(c.source.analysis)

import os
import functools
import jinja2
import logging

from elstir import utils
from elstir.utils import filters
from elstir.config.base import ValidationError

log = logging.getLogger(__name__)


class Theme:
    """
    A Theme object.

    Keywords:

        name: The name of the theme as defined by its entrypoint.

        custom_dir: User defined directory for custom templates.

        static_templates: A list of templates to render as static pages.

    All other keywords are passed as-is and made available as a key/value mapping.

    """

    def __init__(self, name=None, **user_config):
        self.name = name
        self._vars = {}

        # elstir provided static templates are always included
        package_dir = os.path.abspath(os.path.dirname(__file__))
        elstir_templates = os.path.join(package_dir, 'templates')
        elstir_layouts =  os.path.join(package_dir, 'templates')

        self.static_templates = set(os.listdir(elstir_templates))

        # Build self.dirs from various sources in order of precedence
        self.dirs = []

        if 'custom_dir' in user_config:
            self.dirs.append(user_config.pop('custom_dir'))

        if self.name:
            self._load_theme_config(name)

        # Include templates provided directly by elstir (outside any theme)
        self.dirs.append(elstir_templates)

        # Handle remaining user configs. Override theme configs (if set)
        self.static_templates.update(user_config.pop('static_templates', []))
        self._vars.update(user_config)

    def __repr__(self):
        return "{}(name='{}', dirs={}, static_templates={}, {})".format(
            self.__class__.__name__, self.name, self.dirs, list(self.static_templates),
            ', '.join('{}={}'.format(k, repr(v)) for k, v in self._vars.items())
        )

    def __getitem__(self, key):
        return self._vars[key]

    def __setitem__(self, key, value):
        self._vars[key] = value

    def __contains__(self, item):
        return item in self._vars

    def __iter__(self):
        return iter(self._vars)

    def _load_theme_config(self, name):
        """ Recursively load theme and any parent themes. """

        theme_dir = utils.get_theme_dir(name)
        self.dirs.append(theme_dir)

        try:
            file_path = os.path.join(theme_dir, 'elstir_theme.yml')
            with open(file_path, 'rb') as f:
                theme_config = utils.yaml_load(f)
                if theme_config is None:
                    theme_config = {}
        except OSError as e:
            file_path = os.path.join(theme_dir, 'mkdocs_theme.yml')
            with open(file_path, 'rb') as f:
                theme_config = utils.yaml_load(f)
                if theme_config is None:
                    theme_config = {}
        except Exception as e:
            log.debug(e)
            raise ValidationError(
                "The theme '{}' does not appear to have a configuration file. "
                "Please upgrade to a current version of the theme.".format(name)
            )

        log.debug("Loaded theme configuration for '%s' from '%s': %s", name, file_path, theme_config)

        parent_theme = theme_config.pop('extends', None)
        if parent_theme:
            themes = utils.get_theme_names()
            if parent_theme not in themes:
                raise ValidationError(
                    "The theme '{}' inherits from '{}', which does not appear to be installed. "
                    "The available installed themes are: {}".format(name, parent_theme, ', '.join(themes))
                )
            self._load_theme_config(parent_theme)

        self.static_templates.update(theme_config.pop('static_templates', []))
        self._vars.update(theme_config)

    def get_env(self):
        """ Return a Jinja environment for the theme. """

        loader = jinja2.FileSystemLoader(self.dirs)
        # No autoreload because editing a template in the middle of a build is not useful.
        #env = jinja2.Environment(loader=loader, auto_reload=False)
        env = jinja2.Environment(loader=loader, extensions=['jinja2.ext.do'])
        env.filters['tojson'] = filters.tojson
        env.filters['list'] = list
        env.filters['print_console'] = lambda x: print("Template: {}".format(x))
        env.filters['url'] = filters.url_filter
        env.filters['sidebar'] = filters.sidebar
        env.filters['get_children'] = filters.get_children
        env.filters['dirname'] = os.path.dirname
        env.filters['merge_dicts'] = lambda args: functools.reduce(lambda x,y: {**x,**y}, args)
        env.filters['elstir_get_filters'] =  filters.elstir_get_filters
        return env


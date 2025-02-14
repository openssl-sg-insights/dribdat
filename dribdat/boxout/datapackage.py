"""Boxout module for Data Packages."""

import re
import logging
import pystache
from frictionless import Package

TEMPLATE_PACKAGE = r"""
<div class="boxout datapackage card mb-4" style="max-width:23em">
  <div class="card-body">
    <a href="{{homepage}}">
        <h5 class="card-title font-weight-bold">{{title}}</h5>
    </a>
    <a href="{{url}}" download>
        <h6 class="card-subtitle mb-2 text-muted">Data Package</h6>
    </a>
    <div class="card-text description">{{description}}</div>
    <ul class="resources list-unstyled">
    {{#resources}}
        <li><a href="{{path}}" download class="card-link">{{name}}</a>
        <span class="schema-fields">{{#schema.fields}}
            <b title="{{type}}">&#9632;</b>
        {{/schema.fields}}</span></li>
    {{/resources}}
    </ul>
    <div class="details font-size-small">
        <div class="sources float-left">&#128230;
        {{#sources}}
            <a href="{{path}}">{{name}}</a>
        {{/sources}}
        </div>
        {{#licenses}}
        <i class="created">{{created}}</i>
            &nbsp;
        <i class="version">{{version}}</i>
            &nbsp;
        <a class="license" target="_top"
           href="{{path}}" title="{{title}}">License</a>
        {{/licenses}}
    </div>
  </div>
</div>
"""

dpkg_url_re = re.compile(r'.*(http?s:\/\/.+datapackage\.json)\)*')


def chk_datapackage(line):
    """Check the url matching dataset pattern."""
    return (
        (line.startswith('http') and line.endswith('datapackage.json'))
        or line.endswith('datapackage.json)'))


def box_datapackage(line, cache=None):
    """Create a OneBox for local projects."""
    m = dpkg_url_re.match(line)
    if not m:
        return None
    url = m.group(1)
    if cache and cache.has(url):
        return cache.get(url)
    try:
        logging.info("Fetching Data Package: <%s>" % url)
        package = Package(url)
    except Exception:  # noqa: B902
        logging.warn("Data Package not parsed: <%s>" % url)
        return None
    box = pystache.render(TEMPLATE_PACKAGE, package)
    if cache:
        cache.set(url, box)
    if cache and cache.has(url):
        logging.debug("Cached Data Package: <%s>" % url)
    return box

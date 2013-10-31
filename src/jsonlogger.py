'''
This library is provided to allow standard python logging
to output log data as JSON formatted strings
'''
import logging
import json
import re
import datetime

#Support order in python 2.7 and 3
try:
    from collections import OrderedDict
except ImportError:
    pass

# skip natural LogRecord attributes
# http://docs.python.org/library/logging.html#logrecord-attributes
RESERVED_ATTRS = (
    'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
    'funcName', 'levelname', 'levelno', 'lineno', 'module',
    'msecs', 'message', 'msg', 'name', 'pathname', 'process',
    'processName', 'relativeCreated', 'thread', 'threadName')

RESERVED_ATTR_HASH = dict(zip(RESERVED_ATTRS, RESERVED_ATTRS))


def merge_record_extra(record, target, reserved=RESERVED_ATTR_HASH):
    """
    Merges extra attributes from LogRecord object into target dictionary

    :param record: logging.LogRecord
    :param target: dict to update
    :param reserved: dict or list with reserved keys to skip
    """
    for key, value in record.__dict__.iteritems():
        #this allows to have numeric keys
        if (
            key not in reserved
            and not (hasattr(key, "startswith") and key.startswith('_'))
        ):
            target[key] = value
    return target


class JsonFormatter(logging.Formatter):
    """
    A custom formatter to format logging records as json strings.
    extra values will be formatted as str() if nor supported by
    json default encoder
    """

    def __init__(self, *args, **kwargs):
        """
        :param json_default: a function for encoding non-standard objects
            as outlined in http://docs.python.org/2/library/json.html
        :param json_encoder: optional custom encoder
        """
        self.json_default = kwargs.pop("json_default", None)
        self.json_encoder = kwargs.pop("json_encoder", None)
        super(JsonFormatter, self).__init__(*args, **kwargs)
        if not self.json_encoder and not self.json_default:
            def _default_json_handler(obj):
                '''Prints dates in ISO format'''
                if isinstance(obj, datetime.datetime):
                    return obj.strftime(self.datefmt or '%Y-%m-%dT%H:%M')
                elif isinstance(obj, datetime.date):
                    return obj.strftime('%Y-%m-%d')
                elif isinstance(obj, datetime.time):
                    return obj.strftime('%H:%M')
                return unicode(obj)
            self.json_default = _default_json_handler
        self._required_fields = self.parse()
        self._skip_fields = dict(zip(self._required_fields,
                                     self._required_fields))
        self._skip_fields.update(RESERVED_ATTR_HASH)

    def parse(self):
        """Parses format string looking for substitutions"""
        standard_formatters = re.compile(r'\((.+?)\)', re.IGNORECASE)
        return standard_formatters.findall(self._fmt)

    def formatException(self, ei):
        """
        Format and return the specified exception information as a dictonary
        """
        detail = {}
        detail['type'] = ei[0].__name__
        detail['value'] = ei[1]
        tb = ei[2]
        frames = []
        while tb is not None:
            f = tb.tb_frame
            co = f.f_code
            frames.append({'file': co.co_filename, 'ln': tb.tb_lineno, 'fn': co.co_name})
            tb = tb.tb_next

        detail['trace'] = frames

        return detail

    def format(self, record):
        """Formats a log record and serializes to json"""
        extras = {}
        if isinstance(record.msg, dict):
            extras = record.msg
            record.message = None
        else:
            record.message = record.getMessage()
        # only format time if needed
        if "asctime" in self._required_fields:
            record.asctime = self.formatTime(record, self.datefmt)

        try:
            log_record = OrderedDict()
        except NameError:
            log_record = {}

        for field in self._required_fields:
            log_record[field] = record.__dict__[field]
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            log_record['exc'] = record.exc_text

        log_record.update(extras)
        merge_record_extra(record, log_record, reserved=self._skip_fields)

        return json.dumps(log_record,
                          default=self.json_default,
                          cls=self.json_encoder)


class ExtraTextFormatter(logging.Formatter):
    """
    A custom formatter to format logging records as regular strings.
    extra values will be formatted as str() if nor supported by
    json default encoder
    """

    def __init__(self, *args, **kwargs):
        """
        Will record values in the formatter so that we can skip
        """
        super(ExtraTextFormatter, self).__init__(*args, **kwargs)
        self._required_fields = self.parse()
        self._skip_fields = dict(zip(self._required_fields,
                                     self._required_fields))
        self._skip_fields.update(RESERVED_ATTR_HASH)

    def parse(self):
        """Parses format string looking for substitutions"""
        standard_formatters = re.compile(r'\((.+?)\)', re.IGNORECASE)
        return standard_formatters.findall(self._fmt)

    def format(self, record):
        """Formats a log record and serializes to json"""
        extras = {}
        if isinstance(record.msg, dict):
            for key, val in record.msg.iteritems():
                setattr(record, str(key), val)
            record.msg = ''

        line = super(ExtraTextFormatter, self).format(record)

        merge_record_extra(record, extras, reserved=self._skip_fields)

        line += ' ' + ', '.join(["%s: %s" % (key, val) for key, val in extras.iteritems()])

        return line

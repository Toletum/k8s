import logging

LABELS = {
    "domain": "toletum.org",
    "version": "v1",
    "name": "mongodaemon",
    "manifest": "ds_manifest.yaml",
    "operator": "mongodaemons.toletum.org",
    "mongodb_node": "mongo-toletum-org-mongodb",
    "daemonset_status": "mongodaemons.toletum.org.status",
    "primary_label": "mongo-toletum-org-primary",
    "disabled_label": "mongo-toletum-org-disabled"
}

logger = logging.getLogger(LABELS['operator'])
logging.basicConfig(level=logging.INFO)

import datetime
from xml.etree.ElementTree import ElementTree, fromstring

from .version import NeoForgeVersion


class MavenMetadata:
    def __init__(self, xml_tree: ElementTree):
        self.tree = xml_tree

    @property
    def versions(self) -> list[str]:
        return [
            x
            for i in self.tree.findall('./versioning/versions/version')
            if (x := i.text) is not None
        ]

    @property
    def sorted_versions(self):
        return list(
            sorted(
                [NeoForgeVersion.parse(i) for i in self.versions],
                reverse=True
            )
        )

    @property
    def latest_version(self) -> str:
        return self.tree.findtext("./versioning/latest")

    @property
    def release_version(self) -> str:
        return self.tree.findtext("./versioning/release")

    @property
    def group_id(self):
        return self.tree.findtext('./groupId')

    @property
    def artifact_id(self):
        return self.tree.findtext('./artifactId')

    @property
    def last_updated(self):
        elem = self.tree.find('./versioning/lastUpdated')
        if elem is None or not elem.text:
            return None
        return datetime.datetime.strptime(
            elem.text,
            '%Y%m%d%H%M%S'
        )

    @classmethod
    def from_string(cls, s):
        return cls(ElementTree(fromstring(s)))

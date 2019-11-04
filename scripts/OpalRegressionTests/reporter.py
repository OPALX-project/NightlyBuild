import xml.dom
import xml.dom.minidom
import re

class Reporter:

    __shared_state = {}
    def __init__(self):
        #BORG DP
        self.__dict__ = self.__shared_state

    def appendReport(self, string):
        rep = getattr(self, '_report', None)
        if rep is None:
            self._report = string
        else:
            self._report += string

    def getReport(self):
        return getattr(self, '_report', None)

    def NrFailed(self):
        return self._report.count("failed")

    def NrBroken(self):
        return self._report.count("broken")

    def appendChild(self, element):
        root = getattr(self, 'root_element', None)
        if root is None:
            self.xml_report = xml.dom.minidom.Document()
            self.root_element = self.xml_report.createElement("Tests")
            self.xml_report.appendChild(self.root_element)

        self.root_element.appendChild(element.node())

    def getDom(self):
        root = getattr(self, 'root_element', None)
        if root is None:
            self.xml_report = xml.dom.minidom.Document()
            self.root_element = self.xml_report.createElement("Tests")
            self.xml_report.appendChild(self.root_element)

        return self.xml_report

    def dumpXML(self, filename, plots_dir):
        xmlRep = getattr(self, 'xml_report', None)
        if not xmlRep:
            return
        pi = xmlRep.createProcessingInstruction(
            'xml-stylesheet',
            'type="text/xsl" href="results.xslt"')
        root = xmlRep.firstChild
        xmlRep.insertBefore (pi, root)
        content = self.xml_report.toprettyxml(indent='  ').format(plots_dir)
        f = open (filename, "w")
        try:
            f.write (content)
        finally:
            f.close ()


class TempXMLElement:
    def __init__(self, name):
        rep = Reporter()
        self.xml_report = rep.getDom()
        self.root_element = self.xml_report.createElement(name)
        self.current_root = self.root_element

    def appendChild(self, element):
        self.current_root.appendChild(element.node())

    def addAttribute(self, name, value):
        self.current_root.setAttribute(name, value)

    def appendTextNode(self, text):
        element = self.xml_report.createTextNode(text)
        self.current_root.appendChild(element)

    def node(self):
        return self.root_element

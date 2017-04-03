<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:template match="/">
    <html>
    <style type="text/css">
    a { text-decoration:none; color:#666; }
    a:hover { text-decoration:underline; color:#f00;}
    .no-hover {text-decoration:none; color:#000;}
    .no-hover:hover {text-decoration:none; color:#000;}
    </style>
    <body>
        <h2><a name="test_revision" class="no-hover">Revisions</a></h2>
        <table border="0">
          <tr bgcolor="#9acd32">
            <th>Date</th>
            <th>Code</th>
            <th>Tests</th>
          </tr>
          <tr>
            <xsl:variable name="code_hash" select="Tests/Revisions/code_full"/>
            <xsl:variable name="tests_hash" select="Tests/Revisions/tests_full"/>
            <td style="padding: 0px 10px 0px 10px"><xsl:value-of select="Tests/Date/start"/></td>
            <td style="padding: 0px 10px 0px 10px">
              <a href="https://gitlab.psi.ch/OPAL/src/commit/{$code_hash}">
                <xsl:value-of select="Tests/Revisions/code"/>
              </a>
            </td>
            <td style="padding: 0px 10px 0px 10px">
              <a href="https://gitlab.psi.ch/OPAL/regression-tests/commit/{$tests_hash}">
                <xsl:value-of select="Tests/Revisions/tests"/>
              </a>
            </td>
          </tr>
        </table>
        <h2>Regression Tests</h2>
        <xsl:for-each select="Tests/Simulation">
            <xsl:variable name="simname" select="@name"/>
            <h3>Simulation: <xsl:value-of select="@name"/></h3>
            Description: <xsl:value-of select="@description"/>
            <table border="0">
            <tr bgcolor="#9acd32">
                <th>Variable</th>
                <th>Mode</th>
                <th>Required Accuracy</th>
                <th>Delta</th>
                <th>Status</th>
                <th>Plot</th>
            </tr>
            <xsl:for-each select="Test">
                <xsl:choose>
                    <xsl:when test="contains(passed,'true')">
                    <tr>
                        <td><xsl:value-of select="@var"/></td>
                        <td><xsl:value-of select="@mode"/></td>
                        <td><xsl:value-of select="eps"/></td>
                        <td><xsl:value-of select="delta"/></td>
                        <td align="center"><img src="ok.png"/></td>
                        <td>
                            <xsl:variable name="plotname" select="plot"/>
                            <xsl:if test="$plotname">
                                <xsl:variable name="varname" select="@var"/>
                                <a href="#{$simname}_{$varname}">show...</a>
                            </xsl:if>
                        </td>
                    </tr>
                    </xsl:when>
                    <xsl:otherwise>
                    <tr bgcolor="#cdba2d">
                        <td><xsl:value-of select="@var"/></td>
                        <td><xsl:value-of select="@mode"/></td>
                        <td><xsl:value-of select="eps"/></td>
                        <td><xsl:value-of select="delta"/></td>
                        <td align="center"><img src="nok.png"/></td>
                        <td>
                            <xsl:variable name="plotname" select="plot"/>
                            <xsl:if test="$plotname">
                                <xsl:variable name="varname" select="@var"/>
                                <a href="#{$simname}_{$varname}">show...</a>
                            </xsl:if>
                        </td>
                    </tr>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:for-each>
        </table><br/>
        </xsl:for-each>

        <br/>
        <hr/>
        <h2>Plots</h2>
        <xsl:for-each select="Tests/Simulation">
                <xsl:variable name="simname" select="@name"/>
            <h3>Simulation: <xsl:value-of select="@name"/></h3>
            <xsl:for-each select="Test">
                <xsl:variable name="plotname" select="plot"/>
                <xsl:if test="$plotname">
                    <!--<xsl:value-of select="@var"/>:<br/>-->
                    <xsl:variable name="varname" select="@var"/>
                    <a name="{$simname}_{$varname}">
                        <img style="margin-right:3px; margin-bottom:3px;" src="{plot}" alt="" title="" />
                    </a>
<!--                    <div style="width:100%; text-align:right">-->
                        <a href="#test_revision">
                            top &#8593;
                        </a>
<!--                    </div>-->
                    <br/><br/>
                </xsl:if>

            </xsl:for-each>
        <br/>
        </xsl:for-each>

    </body>
    </html>
    </xsl:template>

</xsl:stylesheet>
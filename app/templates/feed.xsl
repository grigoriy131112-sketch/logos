<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html" encoding="UTF-8" indent="yes"/>

  <xsl:template match="/rss/channel">
    <html lang="ru">
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title>Логос — RSS-лента</title>
        <style>
          :root { --paper:#f7f3ec; --raised:#fffdf8; --ink:#221f1a; --soft:#5b544a;
                  --faint:#8a8175; --line:#e2dacd; --accent:#9c3b1f; --gold:#b8863b; }
          body { margin:0; background:var(--paper); color:var(--ink);
                 font-family:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif; line-height:1.6; }
          .wrap { width:min(760px,92vw); margin:0 auto; padding:48px 0 70px; }
          .mark { font-size:26px; width:44px; height:44px; display:grid; place-items:center;
                  color:#fff; background:linear-gradient(145deg,var(--accent),#7a2c14);
                  border-radius:12px; font-family:Georgia,serif; margin-bottom:18px; }
          h1 { font-family:Georgia,"Times New Roman",serif; font-size:38px; margin:0 0 8px; }
          .note { color:var(--faint); font-size:15px; margin:0 0 6px; }
          .sub { color:var(--soft); margin:0 0 34px; }
          .item { border-top:1px solid var(--line); padding:22px 0; }
          .item a { font-family:Georgia,serif; font-size:23px; color:var(--ink);
                    text-decoration:none; }
          .item a:hover { color:var(--accent); }
          .meta { color:var(--faint); font-size:13.5px; margin:6px 0 8px; }
          .desc { color:var(--soft); margin:0; }
          .back { display:inline-block; margin-top:34px; color:var(--accent);
                  text-decoration:none; }
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="mark">Λ</div>
          <h1><xsl:value-of select="title"/></h1>
          <p class="note">Это RSS-лента. Так её видят браузеры — добавьте адрес
            <strong>/feed.xml</strong> в любую программу для чтения RSS.</p>
          <p class="sub"><xsl:value-of select="description"/></p>

          <xsl:for-each select="item">
            <div class="item">
              <a>
                <xsl:attribute name="href"><xsl:value-of select="link"/></xsl:attribute>
                <xsl:value-of select="title"/>
              </a>
              <div class="meta">
                <xsl:value-of select="author"/>
                <xsl:if test="author"> · </xsl:if>
                <xsl:value-of select="pubDate"/>
              </div>
              <p class="desc"><xsl:value-of select="description"/></p>
            </div>
          </xsl:for-each>

          <a class="back">
            <xsl:attribute name="href"><xsl:value-of select="link"/></xsl:attribute>
            ← Перейти на сайт
          </a>
        </div>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>

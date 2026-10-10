#!/usr/bin/env python3
import base64
import os
import json
import re

from watermark import watermark_bytes

BASE = os.path.dirname(os.path.abspath(__file__))

# Which product photos actually exist yet (images/<key>.jpg) — flip to True once uploaded
# (this HAS_PHOTO dict is only used by the Home page hero + "A Few Favourites" teaser)
HAS_PHOTO = {
    "hero": True,
    "wreaths": False,
    "hatbox": True,
    "gravepots": False,
    "bobo": True,
    "rosebear": True,
}

# ---------------- PORTFOLIO GALLERY ----------------
# This drives the full Portfolio page gallery (filters + lightbox), which is built to
# hold lots of photos over time. To add a new photo:
#   1. Watermark it: python3 watermark.py images/hatbox-2.jpg
#      (stamps the "Made With Love" diagonal watermark used across the site —
#      catalogue photos get this automatically on every rebuild, but a photo
#      added here by hand needs this one extra step first)
#   2. Put the (now watermarked) image file in images/ (e.g. images/hatbox-2.jpg)
#   3. Add one entry to GALLERY_ITEMS below (category must match a name in GALLERY_CATEGORIES)
#   4. Re-run this script and re-upload the new image + the changed portfolio.html to GitHub
# That's it — the filter tabs, grid layout and "coming soon" placeholders all update
# automatically; nothing else needs to change.

GALLERY_CATEGORIES = [
    {"name": "Wreaths", "icon": "\U0001F342"},
    {"name": "Hat Boxes", "icon": "\U0001F3A9"},
    {"name": "Handbag Bouquets", "icon": "\U0001F45C"},
    {"name": "Grave Pots", "icon": "\U0001F33F"},
    {"name": "Bobo Balloons", "icon": "\U0001F388"},
    {"name": "Rose Bears", "icon": "\U0001F9F8"},
]

GALLERY_ITEMS = [
    {"category": "Hat Boxes", "file": "rosebear.jpg", "alt": "Made With Love — rose hat box arrangement", "caption": "Rose hat box arrangement"},
    {"category": "Handbag Bouquets", "file": "hatbox.jpg", "alt": "Made With Love — handbag bouquet arrangement", "caption": "Handbag bouquet arrangement"},
    # Reuses the same photo already saved for the Price List's Summer Dream
    # entry (images/catalogue/summer-dream-67fae52e.jpg) rather than
    # needing a separate upload - one photo, shown in two places.
    {"category": "Wreaths", "file": "catalogue/summer-dream-67fae52e.jpg", "alt": "Made With Love — Summer Dream wreath", "caption": "Summer Dream wreath"},
]

# ---------------- PRICE LIST ----------------
# Drives the Price List page. Unlike the gallery above, this list isn't
# hand-typed — it's generated from catalogue-data.json, an export from the
# private "MWL Florals Catalogue" stock-tracking app (its own "Backup"
# button). That app also tracks cost price, stock levels and supplier for
# her own use, but load_catalogue_items() below only ever reads name,
# category, price, description and photo out of it — cost/stock/supplier
# never make it into this script's output, so there's no way for them to
# accidentally end up on the public site.
#
# To update prices on the site: open the catalogue app, tap Backup, save
# the downloaded file over catalogue-data.json in this folder, then
# re-run this script and re-upload the changed pricelist.html + any new
# files under images/catalogue/ to GitHub.

CATALOGUE_CATEGORY_ICONS = {
    "Wreaths": "\U0001F342",
    "Hat Boxes": "\U0001F3A9",
    "Handbag Bouquets": "\U0001F45C",
    "Grave Pots": "\U0001F33F",
    "Bobo Balloons": "\U0001F388",
    "Rose Bears": "\U0001F9F8",
    "Envelopes": "\U0001F48C",
    "Halloween": "\U0001F383",
    "Christmas": "\U0001F384",
    "Other": "\U0001F338",
}
CATALOGUE_CATEGORY_ORDER = list(CATALOGUE_CATEGORY_ICONS.keys())


def _slugify(text):
    text = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return text or "item"


def _save_one_catalogue_photo(images_dir, item_id, name, data_url, suffix=""):
    """Decodes one embedded base64 photo (captured by the catalogue app's
    own camera/photo-library picker, already cropped to a square there)
    into a real image file under images/catalogue/ — the same way every
    other photo on this site is referenced, so this page weighs the same
    as any other page instead of ballooning with inline base64 data.
    Returns the path to use in an <img src>, relative to the site root,
    or None if there was no usable photo to save."""
    if not data_url or not data_url.startswith("data:image/"):
        return None
    try:
        header, b64data = data_url.split(",", 1)
        is_png = "image/png" in header
        # Always saved out as .jpg: watermark_bytes re-encodes to JPEG
        # regardless of the source format, so the extension must match.
        filename = "{}-{}{}.jpg".format(_slugify(name), (item_id or "0")[:8], suffix)
        raw_bytes = base64.b64decode(b64data)
        watermarked = watermark_bytes(raw_bytes, is_png=is_png)
        with open(os.path.join(images_dir, filename), "wb") as f:
            f.write(watermarked)
    except (ValueError, TypeError, OSError):
        return None
    return "catalogue/" + filename


def _save_catalogue_photos(images_dir, item_id, name, raw):
    """Same idea as _save_one_catalogue_photo, but for up to 3 photos per
    item. Newer catalogue-app exports carry a "photos" list (added along
    with the in-app crop/preview tool); older exports only ever had a
    single "photo" field, so that's still read as a 1-photo fallback.
    Returns a list of 1-3 site-relative image paths (possibly empty)."""
    photos = raw.get("photos")
    if not isinstance(photos, list) or not photos:
        photos = [raw.get("photo")] if raw.get("photo") else []
    paths = []
    for i, data_url in enumerate(photos[:3]):
        suffix = "" if i == 0 else "-{}".format(i + 1)
        path = _save_one_catalogue_photo(images_dir, item_id, name, data_url, suffix)
        if path:
            paths.append(path)
    return paths


def _cleanup_stale_catalogue_photos(images_dir, catalogue_items):
    """Deletes any file in images/catalogue/ that nothing on the site
    actually points at any more - mainly photos left behind by an item
    that's since been deleted in the catalogue app. Keeps anything a
    current catalogue item's photo_files lists, plus anything hand-
    referenced from GALLERY_ITEMS (e.g. the Portfolio's Summer Dream
    entry, which points at a catalogue photo without that item still
    being in catalogue-data.json). Safe no-op if the folder is missing."""
    if not os.path.isdir(images_dir):
        return
    keep = set()
    for it in catalogue_items:
        for p in it["photo_files"]:
            keep.add(os.path.basename(p))
    for gi in GALLERY_ITEMS:
        f = gi.get("file", "")
        if f.startswith("catalogue/"):
            keep.add(os.path.basename(f))
    for fname in os.listdir(images_dir):
        if fname not in keep:
            os.remove(os.path.join(images_dir, fname))
            print("removed stale catalogue photo:", fname)


def load_catalogue_items():
    """Reads catalogue-data.json (if present — its absence just means an
    empty price list, not an error) and returns the PUBLIC-SAFE subset of
    each item: name, category, price, description, photo. See the module
    comment above for why cost/stock/supplier stop here."""
    path = os.path.join(BASE, "catalogue-data.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    images_dir = os.path.join(BASE, "images", "catalogue")
    os.makedirs(images_dir, exist_ok=True)

    items = []
    for raw in raw_items:
        name = (raw.get("name") or "").strip()
        if not name:
            continue  # nothing worth showing publicly without at least a name
        items.append({
            "name": name,
            "category": raw.get("category") or "Other",
            "price": raw.get("price"),
            "description": (raw.get("description") or "").strip(),
            "photo_files": _save_catalogue_photos(images_dir, raw.get("id"), name, raw),
        })

    items.sort(key=lambda it: it["name"].lower())
    return items


# ---------------- NEWS / BLOG ----------------
# Drives the News page + the Home page's "Latest News" teaser. Like the
# price list, this isn't hand-typed — it's generated from blog-posts.json,
# written by the "Blog Posts" section of the MWL Catalogue app's Website
# Sync feature. Each post is a title, body text, an optional single photo
# (watermarked the same as every other site photo), a date and who
# posted it (Marie or Darren).

def _save_blog_photo(images_dir, post_id, title, data_url):
    """Same idea as _save_one_catalogue_photo, but for a single blog-post
    photo saved under images/blog/. Returns a site-relative image path,
    or None if there's no usable photo."""
    if not data_url or not data_url.startswith("data:image/"):
        return None
    try:
        header, b64data = data_url.split(",", 1)
        is_png = "image/png" in header
        filename = "{}-{}.jpg".format(_slugify(title), (post_id or "0")[:8])
        raw_bytes = base64.b64decode(b64data)
        watermarked = watermark_bytes(raw_bytes, is_png=is_png)
        with open(os.path.join(images_dir, filename), "wb") as f:
            f.write(watermarked)
    except (ValueError, TypeError, OSError):
        return None
    return "blog/" + filename


def _cleanup_stale_blog_photos(images_dir, blog_posts):
    """Deletes any file in images/blog/ that no current post points at
    any more — mainly a photo left behind by an edited or deleted post.
    Safe no-op if the folder is missing."""
    if not os.path.isdir(images_dir):
        return
    keep = set()
    for p in blog_posts:
        if p["photo_file"]:
            keep.add(os.path.basename(p["photo_file"]))
    for fname in os.listdir(images_dir):
        if fname not in keep:
            os.remove(os.path.join(images_dir, fname))
            print("removed stale blog photo:", fname)


def load_blog_posts():
    """Reads blog-posts.json (if present — its absence just means no news
    content yet, not an error) and returns posts newest first."""
    path = os.path.join(BASE, "blog-posts.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw_posts = json.load(f)

    images_dir = os.path.join(BASE, "images", "blog")
    os.makedirs(images_dir, exist_ok=True)

    posts = []
    for raw in raw_posts:
        title = (raw.get("title") or "").strip()
        body = (raw.get("body") or "").strip()
        if not title or not body:
            continue  # nothing worth publishing without both
        post_id = raw.get("id") or _slugify(title)
        posts.append({
            "id": post_id,
            "title": title,
            "body": body,
            "date": (raw.get("date") or "").strip(),
            "author": (raw.get("author") or "").strip(),
            "photo_file": _save_blog_photo(images_dir, post_id, title, raw.get("photo")),
        })

    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def _esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def currency(n):
    # None/blank shouldn't happen (price is a required field in the
    # catalogue app), but showing "£0.00" for a missing value would read
    # as a genuinely free item - "POA" is a safer fallback than a wrong price.
    try:
        return "£{:.2f}".format(float(n))
    except (TypeError, ValueError):
        return "POA"


def pricelist_section(items):
    """Builds the "Our Work & Price List" page from load_catalogue_items()'s
    output: every category is its own section (photo cards with name,
    description and price), with buttons at the top that jump to each
    section. Everything is rendered server-side up front."""
    if not items:
        return """
<section class="arrangements" id="price-list">
  <div class="wrap">
    <div class="gallery-empty">
      <span class="ge-icon">&#127800;</span>
      Prices are being added right now &mdash; check back soon, or get in touch for a quote.
    </div>
  </div>
</section>
"""

    present = [c for c in CATALOGUE_CATEGORY_ORDER if any(it["category"] == c for it in items)]
    present += sorted({it["category"] for it in items if it["category"] not in present})

    def cat_id(cat):
        return "cat-" + _slugify(cat)

    # Jump buttons (no "All" — every category is already on the page as its
    # own section, so people just scroll, or tap a button to jump to one).
    filter_btns = "\n      ".join(
        '<a class="filter-btn" href="#{cid}">{icon} {cat_label}</a>'.format(
            cid=cat_id(cat),
            icon=CATALOGUE_CATEGORY_ICONS.get(cat, "\U0001F338"),
            cat_label=_esc(cat),
        )
        for cat in present
    )

    def card_html(it):
        icon = CATALOGUE_CATEGORY_ICONS.get(it["category"], "\U0001F338")
        photos = it["photo_files"]
        if not photos:
            photo_html = '<span class="ph-icon">{}</span>'.format(icon)
        elif len(photos) == 1:
            photo_html = '<img src="images/{}" alt="Made With Love — {}" loading="lazy">'.format(_esc(photos[0]), _esc(it["name"]))
        else:
            # More than one photo: a small swipeable gallery (native touch
            # scroll-snap, no JS needed for the swipe itself) with dots that
            # show and set the current slide.
            slides = "".join(
                '<img src="images/{}" alt="Made With Love — {} (photo {} of {})" loading="lazy">'.format(
                    _esc(p), _esc(it["name"]), i + 1, len(photos)
                )
                for i, p in enumerate(photos)
            )
            dots = "".join(
                '<span class="g-dot{active}" data-i="{i}"></span>'.format(active=" active" if i == 0 else "", i=i)
                for i in range(len(photos))
            )
            photo_html = (
                '<div class="price-gallery">{slides}</div>'
                '<div class="g-dots">{dots}</div>'
            ).format(slides=slides, dots=dots)
        desc_html = '<p class="price-desc">{}</p>'.format(_esc(it["description"])) if it["description"] else ""
        return """
      <div class="price-card" data-category="{category}">
        <div class="price-photo{has_photo}{multi}">{photo_html}</div>
        <div class="price-body">
          <span class="price-cat">{category}</span>
          <h3 class="price-name">{name}</h3>
          {desc_html}
          <div class="price-tag">{price}</div>
        </div>
      </div>""".format(
            category=_esc(it["category"]), has_photo=" has-photo" if photos else "",
            multi=" multi-photo" if len(photos) > 1 else "",
            photo_html=photo_html, name=_esc(it["name"]), desc_html=desc_html, price=currency(it["price"]),
        )

    sections = "".join(
        """
    <div class="price-section" id="{cid}">
      <h2 class="price-section-title"><span class="ps-icon">{icon}</span> {label}</h2>
      <div class="price-grid">{cards}
      </div>
    </div>""".format(
            cid=cat_id(cat),
            icon=CATALOGUE_CATEGORY_ICONS.get(cat, "\U0001F338"),
            label=_esc(cat),
            cards="".join(card_html(it) for it in items if it["category"] == cat),
        )
        for cat in present
    )

    return """
<section class="arrangements" id="price-list">
  <div class="wrap">
    <div class="gallery-filters no-print" id="mwl-price-filters">
      {filter_btns}
    </div>{sections}
    <div style="text-align:center;margin-top:30px;">
      <button type="button" class="btn btn-secondary no-print" id="mwl-print-btn">&#128424;&#65039; Print / Save as PDF</button>
    </div>
    <p class="price-note no-print">Prices shown are correct as of today and may vary for custom colours or sizes &mdash; get in touch to confirm before ordering.</p>
  </div>
</section>

<script>
(function(){{
  var printBtn = document.getElementById('mwl-print-btn');
  if (printBtn) printBtn.addEventListener('click', function() {{ window.print(); }});

  // Multi-photo cards: dots reflect the current swiped-to slide, and are
  // themselves clickable to jump straight to a photo (in case someone's
  // on a mouse/trackpad rather than swiping with a finger).
  document.querySelectorAll('.price-photo.multi-photo').forEach(function(wrap) {{
    var gallery = wrap.querySelector('.price-gallery');
    var dots = wrap.querySelectorAll('.g-dot');
    if (!gallery || !dots.length) return;
    var syncTimer = null;
    gallery.addEventListener('scroll', function() {{
      if (syncTimer) clearTimeout(syncTimer);
      syncTimer = setTimeout(function() {{
        var i = Math.round(gallery.scrollLeft / gallery.clientWidth);
        dots.forEach(function(d, di) {{ d.classList.toggle('active', di === i); }});
      }}, 60);
    }}, {{ passive: true }});
    dots.forEach(function(dot) {{
      dot.style.pointerEvents = 'auto';
      dot.style.cursor = 'pointer';
      dot.addEventListener('click', function() {{
        gallery.scrollTo({{ left: Number(dot.dataset.i) * gallery.clientWidth, behavior: 'smooth' }});
      }});
    }});
  }});
}})();
</script>
""".format(filter_btns=filter_btns, sections=sections)


CSS = """
  :root{
    --cream:#faf5ee; --card:#fffdf9; --hessian:#b89968; --hessian-dark:#8f7350;
    --blush:#eec9cd; --blush-dark:#d98f95; --sage:#a8b99a; --sage-dark:#7c9268;
    --ink:#4a3f35; --ink-soft:#7a6d5e; --radius:14px; --maxw:1120px;
  }
  *{box-sizing:border-box;margin:0;padding:0;}
  html{scroll-behavior:smooth;}
  body{font-family:'Poppins',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;color:var(--ink);background:var(--cream);line-height:1.65;}
  img{max-width:100%;display:block;}
  a{color:inherit;}
  h1,h2,h3{font-family:'Playfair Display',Georgia,serif;}
  .script{font-family:'Dancing Script',cursive;}
  .wrap{max-width:var(--maxw);margin:0 auto;padding:0 24px;}

  header.site-nav{position:sticky;top:0;z-index:50;background:rgba(250,245,238,0.94);border-bottom:1px solid #e9ddc9;backdrop-filter:blur(6px);}
  .nav-inner{display:flex;align-items:center;justify-content:space-between;padding:10px 24px;max-width:var(--maxw);margin:0 auto;gap:16px;}
  .nav-logo{display:flex;align-items:center;gap:12px;text-decoration:none;}
  .nav-logo .nav-word{font-size:1.5rem;color:var(--hessian-dark);font-weight:700;}
  nav.links{display:flex;gap:26px;font-size:15px;font-weight:600;}
  nav.links a{text-decoration:none;color:var(--ink-soft);transition:color .15s;}
  nav.links a:hover,nav.links a.active{color:var(--hessian-dark);}
  .nav-cta{background:var(--hessian-dark);color:#fff;padding:10px 20px;border-radius:24px;font-weight:600;font-size:14px;text-decoration:none;white-space:nowrap;}
  .nav-fb{display:inline-flex;align-items:center;color:var(--ink-soft);transition:color .15s;}
  .nav-fb:hover{color:var(--hessian-dark);}
  .nav-fb svg{width:20px;height:20px;display:block;}
  .nav-toggle{display:none;background:none;border:none;cursor:pointer;padding:6px;align-items:center;justify-content:center;color:var(--hessian-dark);}
  .nav-toggle svg{width:26px;height:26px;display:block;}

  .tag-badge{
    border-radius:50%;
    background:radial-gradient(circle at 32% 28%, #cdae7f, #a9895f 65%, #8a6d47);
    box-shadow:inset 0 0 0 3px rgba(255,255,255,.18), 0 6px 16px rgba(74,63,53,.25);
    display:flex;align-items:center;justify-content:center;position:relative;flex-shrink:0;
  }
  .tag-badge::after{content:'';position:absolute;top:10%;left:50%;transform:translateX(-50%);width:9%;height:9%;border-radius:50%;background:#4a3f35;opacity:.3;}
  .tag-badge .script{color:#fffaf3;text-align:center;line-height:1.05;}
  .tag-badge.nav-badge{width:44px;height:44px;transform:rotate(-8deg);}
  .tag-badge.nav-badge .script{font-size:10px;font-weight:700;}
  .tag-badge.hero-badge{width:120px;height:120px;transform:rotate(-9deg);}
  .tag-badge.hero-badge .script{font-size:22px;font-weight:700;}

  .hero{background:linear-gradient(160deg,#f6e8e2 0%,#faf5ee 45%,#f2ede0 100%);padding:64px 0 60px;border-bottom:1px solid #e9ddc9;position:relative;overflow:hidden;}
  .hero-inner{max-width:var(--maxw);margin:0 auto;padding:0 24px;display:grid;grid-template-columns:1.05fr 0.95fr;gap:48px;align-items:center;}
  .eyebrow{display:inline-block;font-size:12.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--hessian-dark);background:rgba(184,153,104,.15);padding:6px 14px;border-radius:20px;margin-bottom:18px;}
  h1.script-title{font-size:4.2rem;line-height:1;color:var(--hessian-dark);margin-bottom:16px;font-weight:700;}
  .hero p.lead{font-size:1.12rem;color:var(--ink-soft);max-width:50ch;margin-bottom:28px;}
  .hero-ctas{display:flex;gap:14px;flex-wrap:wrap;}
  .btn{display:inline-block;padding:13px 26px;border-radius:26px;font-weight:700;text-decoration:none;font-size:15px;transition:transform .15s, box-shadow .15s;border:none;cursor:pointer;}
  .btn-primary{background:var(--hessian-dark);color:#fff;}
  .btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 18px rgba(143,115,80,.35);}
  .btn-secondary{background:#fff;color:var(--hessian-dark);border:1.5px solid var(--hessian-dark);}
  .btn-secondary:hover{transform:translateY(-2px);}

  .hero-photo-card{background:var(--card);border-radius:var(--radius);padding:16px;box-shadow:0 16px 44px rgba(74,63,53,.14);border:1px solid #eee1d0;position:relative;}
  .placeholder-img{
    aspect-ratio:4/3;border-radius:10px;
    background:linear-gradient(135deg,var(--blush) 0%, #f3e3d8 55%, var(--sage) 100%);
    display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;
    border:2px dashed rgba(143,115,80,.35);
  }
  .placeholder-img .ph-icon{font-size:2.4rem;}
  .placeholder-img .ph-label{font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-soft);font-weight:600;}
  .placeholder-img.has-photo{border:none;background:none;padding:0;display:block;}
  .placeholder-img.has-photo img{width:100%;height:100%;object-fit:cover;border-radius:inherit;}
  .hero-photo-card .tag-badge{position:absolute;top:-22px;right:-14px;}

  section{padding:74px 0;}
  .section-head{max-width:640px;margin:0 auto 44px;text-align:center;}
  .section-head .eyebrow{margin-bottom:14px;}
  .section-head h2{font-size:2.1rem;color:var(--ink);margin-bottom:14px;font-weight:700;}
  .section-head p{color:var(--ink-soft);font-size:1.05rem;}

  .page-hero{background:linear-gradient(160deg,#f6e8e2 0%,#faf5ee 100%);border-bottom:1px solid #e9ddc9;padding:54px 0 50px;text-align:center;}
  .page-hero h1{font-size:2.6rem;color:var(--hessian-dark);margin-bottom:12px;}
  .page-hero p{color:var(--ink-soft);font-size:1.08rem;max-width:640px;margin:0 auto;}

  .about{background:var(--card);border-top:1px solid #eee1d0;border-bottom:1px solid #eee1d0;}
  .about .wrap{max-width:780px;text-align:center;}
  .about h2{font-size:2rem;margin-bottom:18px;}
  .about p{color:var(--ink-soft);font-size:1.08rem;margin-bottom:14px;}

  .arrangements{background:var(--cream);}
  .prod-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:26px;}
  .prod-card{background:var(--card);border:1px solid #eee1d0;border-radius:var(--radius);overflow:hidden;transition:box-shadow .15s, transform .15s;}
  .prod-card:hover{box-shadow:0 14px 34px rgba(74,63,53,.12);transform:translateY(-3px);}
  .prod-card .placeholder-img{aspect-ratio:1/1;border-radius:0;border-width:0 0 2px dashed;border-color:rgba(143,115,80,.25);}
  .prod-card .placeholder-img.has-photo{border:none;}
  .prod-card .prod-body{padding:20px 22px 24px;}
  .prod-card h3{font-size:1.25rem;color:var(--hessian-dark);margin-bottom:8px;}
  .prod-card p{font-size:.93rem;color:var(--ink-soft);}

  .gallery-filters{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-bottom:38px;}
  .filter-btn{background:#fff;border:1.5px solid var(--hessian-dark);color:var(--hessian-dark);font-size:14px;font-weight:700;padding:9px 20px;border-radius:22px;cursor:pointer;transition:background .15s,color .15s;}
  .filter-btn:hover{background:rgba(143,115,80,.1);}
  .filter-btn.active{background:var(--hessian-dark);color:#fff;}
  .gallery-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:22px;}
  .gallery-card{background:var(--card);border:1px solid #eee1d0;border-radius:var(--radius);overflow:hidden;cursor:pointer;transition:box-shadow .15s,transform .15s;position:relative;}
  .gallery-card:hover{box-shadow:0 14px 34px rgba(74,63,53,.14);transform:translateY(-3px);}
  .gallery-card .g-photo{aspect-ratio:1/1;overflow:hidden;}
  .gallery-card .g-photo img{width:100%;height:100%;object-fit:cover;transition:transform .25s;}
  .gallery-card:hover .g-photo img{transform:scale(1.05);}
  .gallery-card .g-cap{padding:12px 14px;font-size:.85rem;color:var(--ink-soft);font-weight:600;}
  .gallery-card .g-tag{position:absolute;top:10px;left:10px;background:rgba(74,63,53,.75);color:#fffaf3;font-size:11px;font-weight:700;letter-spacing:.03em;padding:4px 10px;border-radius:12px;}
  .gallery-card.placeholder{cursor:default;}
  .gallery-card.placeholder:hover{box-shadow:none;transform:none;}
  .gallery-card.placeholder .g-photo{background:linear-gradient(135deg,var(--blush) 0%, #f3e3d8 55%, var(--sage) 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;border:2px dashed rgba(143,115,80,.35);}
  .gallery-card.placeholder .g-icon{font-size:2.2rem;}
  .gallery-card.placeholder .g-label{font-size:.75rem;letter-spacing:.05em;text-transform:uppercase;color:var(--ink-soft);font-weight:600;}
  .gallery-empty{text-align:center;color:var(--ink-soft);font-size:1.02rem;padding:40px 20px;}
  .gallery-empty .ge-icon{font-size:2.4rem;display:block;margin-bottom:12px;}

  .lightbox{display:none;position:fixed;inset:0;z-index:500;background:rgba(30,24,18,.92);align-items:center;justify-content:center;padding:40px;}
  .lightbox.open{display:flex;}
  .lightbox-inner{max-width:min(880px,90vw);max-height:86vh;text-align:center;}
  .lightbox-inner img{max-width:100%;max-height:74vh;border-radius:8px;box-shadow:0 20px 60px rgba(0,0,0,.4);}
  .lightbox-cap{color:#fffaf3;margin-top:16px;font-size:.95rem;}
  .lightbox-close{position:absolute;top:20px;right:28px;background:rgba(255,255,255,.12);border:none;color:#fff;width:42px;height:42px;border-radius:50%;font-size:22px;cursor:pointer;line-height:1;}
  .lightbox-close:hover{background:rgba(255,255,255,.24);}
  .lightbox-nav{position:absolute;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.12);border:none;color:#fff;width:48px;height:48px;border-radius:50%;font-size:22px;cursor:pointer;}
  .lightbox-nav:hover{background:rgba(255,255,255,.24);}
  .lightbox-prev{left:24px;}
  .lightbox-next{right:24px;}

  .why{background:linear-gradient(135deg,#f6e8e2,#eef1e6);}
  .why-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:22px;text-align:center;}
  .why-item{background:rgba(255,253,249,.6);border-radius:var(--radius);padding:26px 18px;}
  .why-item .wi-icon{font-size:1.8rem;margin-bottom:10px;}
  .why-item h4{font-size:1rem;margin-bottom:6px;color:var(--ink);font-family:'Poppins',sans-serif;font-weight:700;}
  .why-item p{font-size:.86rem;color:var(--ink-soft);}

  .contact{background:var(--hessian-dark);color:#fffaf3;}
  .contact .section-head h2{color:#fffaf3;}
  .contact .section-head p{color:#ecdcc4;}
  .contact-card{max-width:560px;margin:0 auto;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);border-radius:var(--radius);padding:34px;text-align:center;}
  .placeholder-badge{display:inline-block;background:var(--blush-dark);color:#fff;font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:5px 12px;border-radius:14px;margin-bottom:18px;}
  .contact-rows{display:flex;flex-direction:column;gap:14px;margin:20px 0 26px;text-align:left;}
  .contact-row{display:flex;gap:12px;align-items:flex-start;background:rgba(255,255,255,.06);padding:14px 16px;border-radius:8px;}
  .contact-row .icon{font-size:18px;}
  .contact-row .label{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#e6d2b8;font-weight:700;}
  .contact-row .val{font-size:15px;font-weight:600;}
  .contact .btn-primary{background:#fff;color:var(--hessian-dark);}
  .contact .btn-primary:hover{box-shadow:0 8px 18px rgba(0,0,0,.25);}
  .contact-form{max-width:560px;margin:34px auto 0;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);border-radius:var(--radius);padding:30px;text-align:left;}
  .contact-form label{display:block;font-size:13px;font-weight:700;margin-bottom:6px;margin-top:14px;color:#f3e6d5;}
  .contact-form label:first-child{margin-top:0;}
  .contact-form input,.contact-form textarea{width:100%;padding:11px 13px;border-radius:8px;border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.95);font-family:inherit;font-size:14px;}
  .contact-form textarea{min-height:100px;resize:vertical;}
  .contact-form button{margin-top:20px;width:100%;}
  .contact-form button:disabled{opacity:.6;cursor:not-allowed;}
  .contact-form .form-status{margin-top:14px;font-size:13.5px;font-weight:700;min-height:18px;}
  .contact-form .form-status.success{color:#bfe8c9;}
  .contact-form .form-status.error{color:#f3b6ab;}
  .contact-form .mwl-honeypot{position:absolute;left:-9999px;opacity:0;}

  footer{background:#3a2f26;color:#c9b79c;padding:30px 0;font-size:13px;}
  .footer-inner{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;}
  .footer-inner .brand{color:#fffaf3;font-family:'Dancing Script',cursive;font-size:1.2rem;}
  .footer-inner .flinks a{color:#c9b79c;text-decoration:none;margin-left:16px;}
  .footer-inner .flinks a:hover{color:#fffaf3;}
  .footer-inner .flinks a.fb-icon{display:inline-flex;align-items:center;vertical-align:middle;}
  .footer-inner .flinks a.fb-icon svg{width:17px;height:17px;display:block;}

  #mwl-chat-launcher{position:fixed;bottom:22px;right:22px;z-index:200;width:60px;height:60px;border-radius:50%;background:var(--hessian-dark);color:#fff;border:none;cursor:pointer;box-shadow:0 8px 24px rgba(74,63,53,.35);font-size:26px;display:flex;align-items:center;justify-content:center;transition:transform .15s;}
  #mwl-chat-launcher:hover{transform:scale(1.06);}
  #mwl-chat-launcher .close-ic{display:none;}
  #mwl-chat-launcher.open .chat-ic{display:none;}
  #mwl-chat-launcher.open .close-ic{display:block;}
  #mwl-chat-badge{position:absolute;top:-4px;right:-4px;background:var(--blush-dark);color:#fff;font-size:10px;font-weight:800;border-radius:10px;padding:2px 6px;}
  #mwl-chat-panel{position:fixed;bottom:94px;right:22px;z-index:200;width:340px;max-width:calc(100vw - 32px);background:#fffdf9;border-radius:14px;overflow:hidden;box-shadow:0 20px 60px rgba(74,63,53,.30);border:1px solid #eee1d0;display:none;flex-direction:column;height:500px;max-height:calc(100vh - 140px);}
  #mwl-chat-panel.open{display:flex;}
  .chat-head{background:var(--hessian-dark);color:#fffaf3;padding:16px 18px;display:flex;align-items:center;gap:10px;flex-shrink:0;}
  .chat-head .dot{width:9px;height:9px;border-radius:50%;background:#8fd0a0;flex-shrink:0;}
  .chat-head .titles{line-height:1.25;}
  .chat-head .titles .t1{font-weight:800;font-size:14px;}
  .chat-head .titles .t2{font-size:11px;color:#ecdcc4;}
  .chat-body{flex:1;overflow-y:auto;padding:16px;background:#faf5ee;display:flex;flex-direction:column;gap:10px;}
  .chat-msg{max-width:85%;padding:10px 13px;border-radius:12px;font-size:13.5px;line-height:1.45;}
  .chat-msg.bot{background:#fff;border:1px solid #eee1d0;color:var(--ink);align-self:flex-start;border-bottom-left-radius:3px;}
  .chat-msg.user{background:var(--hessian-dark);color:#fff;align-self:flex-end;border-bottom-right-radius:3px;}
  .chat-quick{display:flex;flex-wrap:wrap;gap:7px;align-self:flex-start;max-width:100%;}
  .chat-quick button{background:#fff;border:1.3px solid var(--hessian-dark);color:var(--hessian-dark);font-size:12px;font-weight:700;padding:7px 11px;border-radius:16px;cursor:pointer;transition:background .15s, color .15s;}
  .chat-quick button:hover{background:var(--hessian-dark);color:#fff;}
  .chat-live-cta{border-top:1px solid #eee1d0;padding:10px 14px;background:#fff;flex-shrink:0;}
  .chat-live-cta button{width:100%;background:var(--blush-dark);color:#fff;border:none;border-radius:20px;padding:10px;font-weight:700;font-size:13px;cursor:pointer;}
  .chat-live-cta button:hover{background:#c67d83;}
  .chat-foot{border-top:1px solid #eee1d0;padding:10px;display:flex;gap:8px;background:#fff;flex-shrink:0;}
  .chat-foot input{flex:1;border:1px solid #e6dac6;border-radius:20px;padding:9px 14px;font-size:13px;outline:none;}
  .chat-foot input:focus{border-color:var(--hessian-dark);}
  .chat-foot button{background:var(--hessian-dark);color:#fff;border:none;border-radius:20px;padding:0 16px;font-weight:700;font-size:13px;cursor:pointer;}
  .chat-disclaimer{font-size:10px;color:var(--ink-soft);text-align:center;padding:6px 10px 0;background:#fff;}

  @media(max-width:900px){
    .hero-inner{grid-template-columns:1fr;}
    .hero-photo-card{order:-1;max-width:420px;margin:0 auto;}
    .why-grid{grid-template-columns:1fr 1fr;}
    .nav-toggle{display:flex;}
    nav.links{display:none;position:absolute;top:100%;left:0;right:0;flex-direction:column;gap:0;background:#fffaf3;border-bottom:1px solid #e9ddc9;box-shadow:0 14px 30px rgba(74,63,53,.14);padding:4px 24px 10px;}
    nav.links.open{display:flex;}
    nav.links a{padding:13px 4px;border-bottom:1px solid #f1e8d8;}
    nav.links a:last-child{border-bottom:none;}
  }
  @media(max-width:560px){
    h1.script-title{font-size:3rem;}
    .why-grid{grid-template-columns:1fr 1fr;}
    .nav-cta{display:none;}
    #mwl-chat-panel{right:16px;left:16px;width:auto;bottom:88px;}
    #mwl-chat-launcher{right:16px;bottom:16px;}
    .gallery-grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px;}
    .lightbox{padding:16px;}
    .lightbox-nav{width:40px;height:40px;font-size:18px;}
    .lightbox-prev{left:8px;}
    .lightbox-next{right:8px;}
    .lightbox-close{top:10px;right:10px;width:38px;height:38px;}
  }

  /* ---------------- Price List ---------------- */
  .price-section{margin-bottom:46px;scroll-margin-top:84px;}
  .price-section-title{font-size:26px;margin-bottom:18px;color:var(--hessian-dark);display:flex;align-items:center;gap:10px;border-bottom:1.5px solid #e9ddc9;padding-bottom:8px;}
  .price-section-title .ps-icon{font-size:24px;}
  a.filter-btn{text-decoration:none;display:inline-block;}
  .price-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:22px;}
  .price-card{background:var(--card);border:1px solid #eee1d0;border-radius:var(--radius);overflow:hidden;transition:box-shadow .15s,transform .15s;}
  .price-card:hover{box-shadow:0 14px 34px rgba(74,63,53,.14);transform:translateY(-3px);}
  .price-photo{aspect-ratio:1/1;overflow:hidden;background:linear-gradient(135deg,var(--blush) 0%, #f3e3d8 55%, var(--sage) 100%);display:flex;align-items:center;justify-content:center;position:relative;}
  .price-photo .ph-icon{font-size:2.2rem;}
  .price-photo.has-photo{background:none;}
  .price-photo.has-photo img{width:100%;height:100%;object-fit:cover;}
  .price-photo.multi-photo{display:block;}
  .price-gallery{display:flex;width:100%;height:100%;overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;scrollbar-width:none;}
  .price-gallery::-webkit-scrollbar{display:none;}
  .price-gallery img{flex:0 0 100%;width:100%;height:100%;object-fit:cover;scroll-snap-align:start;}
  .g-dots{position:absolute;left:0;right:0;bottom:8px;display:flex;justify-content:center;gap:6px;pointer-events:none;}
  .g-dot{width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,.55);box-shadow:0 0 0 1px rgba(0,0,0,.12);transition:background .15s,transform .15s;}
  .g-dot.active{background:#fff;transform:scale(1.25);}
  .price-body{padding:16px 18px 20px;}
  .price-cat{font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--hessian-dark);}
  .price-name{font-size:1.1rem;color:var(--ink);margin:6px 0 6px;}
  .price-desc{font-size:.88rem;color:var(--ink-soft);margin-bottom:10px;}
  .price-tag{font-size:1.15rem;font-weight:700;color:var(--hessian-dark);font-variant-numeric:tabular-nums;}
  .price-note{text-align:center;color:var(--ink-soft);font-size:.82rem;margin-top:26px;}

  /* ---------------- News / Blog ---------------- */
  .news-teaser{background:var(--cream);}
  .news-teaser-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:26px;}
  .news-teaser-card{background:var(--card);border:1px solid #eee1d0;border-radius:var(--radius);overflow:hidden;transition:box-shadow .15s,transform .15s;}
  .news-teaser-card:hover{box-shadow:0 14px 34px rgba(74,63,53,.12);transform:translateY(-3px);}
  .news-teaser-photo{aspect-ratio:4/3;overflow:hidden;}
  .news-teaser-photo img{width:100%;height:100%;object-fit:cover;}
  .news-teaser-body{padding:20px 22px 24px;}
  .news-teaser-body h3{font-size:1.15rem;color:var(--hessian-dark);margin-bottom:8px;}
  .post-meta{font-size:.82rem;color:var(--ink-soft);margin-bottom:10px;}
  .news-teaser-link{display:inline-block;margin-top:4px;font-size:.88rem;font-weight:700;color:var(--hessian-dark);text-decoration:none;}
  .news-teaser-link:hover{text-decoration:underline;}

  .news-list .wrap{max-width:720px;}
  .post-card{background:var(--card);border:1px solid #eee1d0;border-radius:var(--radius);overflow:hidden;margin-bottom:32px;}
  .post-card:last-child{margin-bottom:0;}
  .post-photo{aspect-ratio:16/9;overflow:hidden;}
  .post-photo img{width:100%;height:100%;object-fit:cover;}
  .post-body{padding:28px clamp(20px,5vw,34px) 32px;}
  .post-body h2{font-size:1.6rem;color:var(--hessian-dark);margin-bottom:8px;}
  .post-body p{color:var(--ink);font-size:1rem;margin-bottom:14px;}
  .post-body p:last-child{margin-bottom:0;}

  @media print{
    html,body,section,.arrangements{background:#fff !important;}
    header.site-nav,footer,#mwl-chat-launcher,#mwl-chat-panel,.page-hero .eyebrow,.contact,.no-print{display:none !important;}
    .page-hero{background:none;border:0;padding:0 0 20px;}
    .page-hero h1{color:#4a3f35;}
    .gallery-filters{display:none;}
    .price-grid{grid-template-columns:repeat(2,1fr);gap:14px;}
    .price-card{box-shadow:none;border:1px solid #ddd;break-inside:avoid;}
    .price-card:hover{transform:none;box-shadow:none;}
  }

  /* ---------------- Cookie banner ---------------- */
  #cookie-banner{position:fixed;left:0;right:0;bottom:0;z-index:300;background:var(--hessian-dark);color:#fffaf3;padding:16px 20px;box-shadow:0 -6px 24px rgba(0,0,0,.18);}
  #cookie-banner .cookie-inner{max-width:var(--maxw);margin:0 auto;display:flex;flex-wrap:wrap;align-items:center;gap:14px 24px;justify-content:space-between;}
  #cookie-banner p{margin:0;font-size:.9rem;line-height:1.5;color:#fffaf3;flex:1 1 320px;}
  #cookie-banner a{color:#ecdcc4;text-decoration:underline;}
  #cookie-banner .cookie-actions{display:flex;gap:10px;flex-shrink:0;}
  #cookie-banner .btn-cookie{padding:10px 20px;border-radius:22px;font-weight:700;font-size:.85rem;border:none;cursor:pointer;}
  #cookie-accept{background:var(--sage-dark);color:#fff;}
  #cookie-reject{background:transparent;color:#fffaf3;border:1px solid #fffaf3 !important;}
  @media (max-width:640px){
    #cookie-banner .cookie-inner{flex-direction:column;align-items:stretch;}
    #cookie-banner .cookie-actions{justify-content:flex-end;}
  }
  @media print{ #cookie-banner{display:none !important;} }
"""

def placeholder(icon="&#127800;", label="Photo coming soon"):
    return f'<div class="placeholder-img"><span class="ph-icon">{icon}</span><span class="ph-label">{label}</span></div>'


def photo_img(key, alt, icon="&#127800;"):
    """References an external file in images/<key>.jpg — swap the file on GitHub to update the picture, no code changes needed."""
    if not HAS_PHOTO.get(key):
        return placeholder(icon)
    return f'<div class="placeholder-img has-photo"><img src="images/{key}.jpg" alt="{alt}" loading="lazy"></div>'


def merged_gallery_categories(catalogue_items):
    """GALLERY_CATEGORIES (hand-curated — keeps its order, icons and
    "coming soon" placeholders for types with no photo yet) plus any
    catalogue category that isn't already covered, so a catalogue item
    filed under something like "Christmas" or "Other" still gets a
    heading to sit under instead of being silently dropped."""
    existing_names = {c["name"] for c in GALLERY_CATEGORIES}
    extra = []
    for cat_name in CATALOGUE_CATEGORY_ORDER:
        if cat_name in existing_names:
            continue
        if any(it["category"] == cat_name for it in catalogue_items):
            extra.append({"name": cat_name, "icon": CATALOGUE_CATEGORY_ICONS[cat_name]})
    return GALLERY_CATEGORIES + extra


def catalogue_gallery_items(catalogue_items):
    """Turns each catalogue item's saved photo(s) into Portfolio gallery
    entries, filed under its own category — the same photos already
    shown on the Price List, so nothing needs a separate upload just to
    also appear in the Portfolio."""
    out = []
    for it in catalogue_items:
        photos = it["photo_files"]
        for i, path in enumerate(photos):
            caption = it["name"] if len(photos) == 1 else f'{it["name"]} ({i + 1}/{len(photos)})'
            out.append({
                "category": it["category"],
                "file": path,
                "alt": f'Made With Love — {it["name"]}',
                "caption": caption,
            })
    return out


def gallery_section(categories, items):
    """Builds the filterable Portfolio gallery + lightbox. Data-driven from GALLERY_CATEGORIES /
    GALLERY_ITEMS at the top of this file — see the comment there for how to add a photo."""
    filter_btns = '\n      '.join(
        f'<button class="filter-btn{" active" if i == 0 else ""}" data-filter="{"All" if i == 0 else c["name"]}">{"All" if i == 0 else c["name"]}</button>'
        for i, c in enumerate([{"name": "All"}] + categories)
    )
    cats_json = json.dumps(categories)
    items_json = json.dumps(items)
    return f"""
<section class="arrangements" id="portfolio">
  <div class="wrap">
    <div class="gallery-filters">
      {filter_btns}
    </div>
    <div class="gallery-grid" id="mwl-gallery-grid"></div>
  </div>
</section>

<div class="lightbox" id="mwl-lightbox">
  <button class="lightbox-close" id="mwl-lb-close" aria-label="Close">&#10005;</button>
  <button class="lightbox-nav lightbox-prev" id="mwl-lb-prev" aria-label="Previous">&#10094;</button>
  <div class="lightbox-inner">
    <img id="mwl-lb-img" src="" alt="">
    <div class="lightbox-cap" id="mwl-lb-cap"></div>
  </div>
  <button class="lightbox-nav lightbox-next" id="mwl-lb-next" aria-label="Next">&#10095;</button>
</div>

<script>
(function(){{
  var CATS = {cats_json};
  var ITEMS = {items_json};
  var grid = document.getElementById('mwl-gallery-grid');
  var filterBtns = document.querySelectorAll('.filter-btn');
  var currentFilter = 'All';
  var visiblePhotos = [];

  function itemsFor(catName) {{
    return ITEMS.filter(function(it) {{ return it.category === catName; }});
  }}

  function render(filter) {{
    currentFilter = filter;
    grid.innerHTML = '';
    visiblePhotos = [];

    var catsToShow = filter === 'All' ? CATS : CATS.filter(function(c) {{ return c.name === filter; }});

    if (filter !== 'All' && itemsFor(filter).length === 0) {{
      var cat = CATS.filter(function(c) {{ return c.name === filter; }})[0];
      grid.innerHTML = '<div class="gallery-empty" style="grid-column:1/-1;"><span class="ge-icon">' + (cat ? cat.icon : '&#127800;') + '</span>Photos of our ' + filter + ' are coming soon &mdash; ask us directly in the meantime!</div>';
      return;
    }}

    catsToShow.forEach(function(cat) {{
      var photos = itemsFor(cat.name);
      if (photos.length === 0) {{
        var card = document.createElement('div');
        card.className = 'gallery-card placeholder';
        card.innerHTML = '<div class="g-photo"><span class="g-icon">' + cat.icon + '</span><span class="g-label">' + cat.name + ' — coming soon</span></div>';
        grid.appendChild(card);
        return;
      }}
      photos.forEach(function(it) {{
        var idx = visiblePhotos.length;
        visiblePhotos.push(it);
        var card = document.createElement('div');
        card.className = 'gallery-card';
        // Just the photo in the grid — no tag/caption text on top of it,
        // since the Price List page is now what tells people the type of
        // arrangement and what it's called. The category + caption are
        // still there for anyone who taps a photo though - see
        // showLightboxPhoto() below, which keeps setting lbCap's text.
        card.innerHTML = '<div class="g-photo"><img src="images/' + it.file + '" alt="' + it.alt + '" loading="lazy"></div>';
        card.addEventListener('click', function() {{ openLightbox(idx); }});
        grid.appendChild(card);
      }});
    }});
  }}

  filterBtns.forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      filterBtns.forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      render(btn.getAttribute('data-filter'));
    }});
  }});

  var lightbox = document.getElementById('mwl-lightbox');
  var lbImg = document.getElementById('mwl-lb-img');
  var lbCap = document.getElementById('mwl-lb-cap');
  var lbIndex = 0;

  function openLightbox(idx) {{
    lbIndex = idx;
    showLightboxPhoto();
    lightbox.classList.add('open');
  }}
  function showLightboxPhoto() {{
    var it = visiblePhotos[lbIndex];
    if (!it) return;
    lbImg.src = 'images/' + it.file;
    lbImg.alt = it.alt;
    lbCap.textContent = it.caption + ' — ' + it.category;
  }}
  function closeLightbox() {{ lightbox.classList.remove('open'); }}
  function nextPhoto() {{ lbIndex = (lbIndex + 1) % visiblePhotos.length; showLightboxPhoto(); }}
  function prevPhoto() {{ lbIndex = (lbIndex - 1 + visiblePhotos.length) % visiblePhotos.length; showLightboxPhoto(); }}

  document.getElementById('mwl-lb-close').addEventListener('click', closeLightbox);
  document.getElementById('mwl-lb-next').addEventListener('click', nextPhoto);
  document.getElementById('mwl-lb-prev').addEventListener('click', prevPhoto);
  lightbox.addEventListener('click', function(e) {{ if (e.target === lightbox) closeLightbox(); }});
  document.addEventListener('keydown', function(e) {{
    if (!lightbox.classList.contains('open')) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowRight') nextPhoto();
    if (e.key === 'ArrowLeft') prevPhoto();
  }});

  render('All');
}})();
</script>
"""


def _post_anchor(post):
    return "post-" + _slugify(post["title"]) + "-" + (post["id"] or "")[:6]


def _format_post_date(date_str):
    """date_str is "YYYY-MM-DD" from the app's date input; rendered as
    "3 October 2026" when parseable, shown as-is otherwise rather than
    hidden (a post is still worth a date even if the format is odd)."""
    import datetime
    if not date_str:
        return ""
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return "{} {} {}".format(d.day, d.strftime("%B"), d.year)
    except (ValueError, TypeError):
        return date_str


def blog_post_card(post):
    anchor = _post_anchor(post)
    photo_html = ""
    if post["photo_file"]:
        photo_html = '<div class="post-photo"><img src="images/{}" alt="{}" loading="lazy"></div>'.format(
            post["photo_file"], _esc(post["title"])
        )
    meta_bits = []
    date_label = _format_post_date(post["date"])
    if date_label:
        meta_bits.append(_esc(date_label))
    if post["author"]:
        meta_bits.append("by " + _esc(post["author"]))
    meta_html = ""
    if meta_bits:
        meta_html = '<div class="post-meta">{}</div>'.format(" &middot; ".join(meta_bits))
    body_html = "".join(
        "<p>{}</p>".format(_esc(para).replace("\n", "<br>"))
        for para in post["body"].split("\n\n") if para.strip()
    )
    return """
<article class="post-card" id="{anchor}">
  {photo_html}
  <div class="post-body">
    <h2>{title}</h2>
    {meta_html}
    {body_html}
  </div>
</article>
""".format(anchor=anchor, photo_html=photo_html, title=_esc(post["title"]), meta_html=meta_html, body_html=body_html)


def news_body(posts):
    if not posts:
        return """
<section class="news-list">
  <div class="wrap" style="text-align:center;padding:50px 0;">
    <p style="color:var(--ink-soft);font-size:1.05rem;">No news yet &mdash; check back soon.</p>
  </div>
</section>
"""
    cards = "".join(blog_post_card(p) for p in posts)
    return """
<section class="news-list">
  <div class="wrap">{cards}</div>
</section>
""".format(cards=cards)


def blog_teaser_section(posts):
    """Only rendered when there's at least one post, same "no coming soon
    placeholders" approach as the Price List's category tabs."""
    if not posts:
        return ""
    cards = []
    for p in posts[:3]:
        photo_html = ""
        if p["photo_file"]:
            photo_html = '<div class="news-teaser-photo"><img src="images/{}" alt="{}" loading="lazy"></div>'.format(
                p["photo_file"], _esc(p["title"])
            )
        date_label = _format_post_date(p["date"])
        meta_html = '<div class="post-meta">{}</div>'.format(_esc(date_label)) if date_label else ""
        cards.append("""
<div class="news-teaser-card">
  {photo_html}
  <div class="news-teaser-body">
    <h3>{title}</h3>
    {meta_html}
    <a href="news.html#{anchor}" class="news-teaser-link">Read more &rarr;</a>
  </div>
</div>
""".format(photo_html=photo_html, title=_esc(p["title"]), meta_html=meta_html, anchor=_post_anchor(p)))
    return """
<section class="news-teaser" id="news-teaser">
  <div class="wrap">
    <div class="section-head">
      <span class="eyebrow">What's New</span>
      <h2>Latest News</h2>
    </div>
    <div class="news-teaser-grid">{cards}</div>
    <div style="text-align:center;margin-top:28px;">
      <a href="news.html" class="btn btn-secondary">See All News</a>
    </div>
  </div>
</section>
""".format(cards="".join(cards))


# Shared Facebook glyph (single-path "f in a circle" mark) used both in
# the top nav and the footer - colored via currentColor so it always
# matches whatever link color/hover state it's dropped into.
FACEBOOK_URL = "https://www.facebook.com/madewithlove2611"
FB_ICON_SVG = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M22 12.06C22 6.48 17.52 2 11.94 2 6.36 2 1.88 6.48 1.88 12.06c0 5.02 3.66 9.18 8.44 9.94v-7.03H7.9v-2.91h2.42V9.91c0-2.39 1.42-3.71 3.6-3.71 1.04 0 2.13.19 2.13.19v2.35h-1.2c-1.18 0-1.55.74-1.55 1.49v1.79h2.64l-.42 2.91h-2.22V22c4.78-.76 8.44-4.92 8.44-9.94Z"/></svg>'


def nav_html(active):
    items = [("index.html", "Home"), ("pricelist.html", "Our Work &amp; Price List"), ("news.html", "News"), ("about.html", "About"), ("contact.html", "Contact")]
    ACTIVE_CLASS = ' class="active"'
    links = "\n".join(
        f'      <a href="{href}"{ACTIVE_CLASS if href == active else ""}>{label}</a>'
        for href, label in items
    )
    return f"""
<header class="site-nav">
  <div class="nav-inner">
    <a href="index.html" class="nav-logo">
      <div class="tag-badge nav-badge"><span class="script">MWL</span></div>
      <span class="nav-word script">Made With Love</span>
    </a>
    <nav class="links" id="mwl-nav-links">
{links}
    </nav>
    <a href="{FACEBOOK_URL}" class="nav-fb" target="_blank" rel="noopener" aria-label="Made With Love on Facebook">{FB_ICON_SVG}</a>
    <a href="contact.html" class="nav-cta">Get in Touch</a>
    <button type="button" class="nav-toggle" id="mwl-nav-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="mwl-nav-links">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
    </button>
  </div>
</header>
<script>
(function(){{
  var toggle = document.getElementById('mwl-nav-toggle');
  var menu = document.getElementById('mwl-nav-links');
  if (!toggle || !menu) return;
  function closeMenu(){{
    menu.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
  }}
  toggle.addEventListener('click', function(){{
    var isOpen = menu.classList.toggle('open');
    toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }});
  menu.addEventListener('click', function(e){{
    if (e.target.tagName === 'A') closeMenu();
  }});
  document.addEventListener('click', function(e){{
    if (!menu.classList.contains('open')) return;
    if (!menu.contains(e.target) && e.target !== toggle && !toggle.contains(e.target)) closeMenu();
  }});
}})();
</script>
"""

FOOTER = f"""
<footer>
  <div class="wrap footer-inner">
    <div class="brand">Made With Love</div>
    <div>Handmade Artificial Flower Arrangements</div>
    <div class="flinks">
      <a href="index.html">Home</a><a href="pricelist.html">Our Work &amp; Price List</a><a href="news.html">News</a><a href="about.html">About</a><a href="contact.html">Contact</a><a href="privacy.html">Privacy Policy</a><a href="#" id="cookie-settings-link">Cookie Settings</a><a href="{FACEBOOK_URL}" class="fb-icon" target="_blank" rel="noopener" aria-label="Made With Love on Facebook">{FB_ICON_SVG}</a>
    </div>
  </div>
</footer>
"""

COOKIE_BANNER = """
<div id="cookie-banner" hidden role="dialog" aria-label="Cookie notice">
  <div class="cookie-inner">
    <p>We use essential cookies to run this site. If you accept, we'll also load our live chat widget (Tawk.to), which sets its own cookie — see our <a href="privacy.html">Privacy Policy</a> for details. We won't load it unless you say yes.</p>
    <div class="cookie-actions">
      <button type="button" id="cookie-accept" class="btn-cookie">Accept</button>
      <button type="button" id="cookie-reject" class="btn-cookie">Reject</button>
    </div>
  </div>
</div>
"""

CHAT_WIDGET = """
<button id="mwl-chat-launcher" aria-label="Open chat">
  <span class="chat-ic">&#128172;</span>
  <span class="close-ic">&#10005;</span>
  <span id="mwl-chat-badge">?</span>
</button>

<div id="mwl-chat-panel">
  <div class="chat-head">
    <span class="dot"></span>
    <div class="titles">
      <div class="t1">Made With Love</div>
      <div class="t2">Quick answers, or message us directly</div>
    </div>
  </div>
  <div class="chat-body" id="mwl-chat-body"></div>
  <div class="chat-live-cta">
    <button id="mwl-live-chat-btn">&#128172; Talk to a real person</button>
  </div>
  <div class="chat-foot">
    <input type="text" id="mwl-chat-input" placeholder="Ask a question&hellip;" autocomplete="off">
    <button id="mwl-chat-send">Send</button>
  </div>
  <div class="chat-disclaimer">Quick-answers are automated. "Talk to a real person" reaches us directly.</div>
</div>

<!--Start of Tawk.to Script (only loaded after cookie consent — see cookie-consent script below) -->
<script type="text/javascript">
function mwlLoadTawk(){
  if (window.__mwlTawkLoaded) return;
  window.__mwlTawkLoaded = true;
  var Tawk_API=window.Tawk_API||{}, Tawk_LoadStart=new Date();
  window.Tawk_API = Tawk_API;
  window.Tawk_LoadStart = Tawk_LoadStart;
  Tawk_API.onLoad = function(){
    // keep Tawk.to's own floating bubble hidden — "Talk to a real person"
    // above is the only thing that should open it, so we don't end up
    // with two chat bubbles stacked in the corner.
    if (typeof Tawk_API.hideWidget === 'function') { Tawk_API.hideWidget(); }
  };
  var s1=document.createElement("script"),s0=document.getElementsByTagName("script")[0];
  s1.async=true;
  s1.src='https://embed.tawk.to/6a70e89608d7a41d4157837c/1jv4gp2uq';
  s1.charset='UTF-8';
  s1.setAttribute('crossorigin','*');
  s0.parentNode.insertBefore(s1,s0);
}
</script>
<!--End of Tawk.to Script-->

<!--Start of cookie consent banner-->
<script type="text/javascript">
(function(){
  var banner = document.getElementById('cookie-banner');
  var acceptBtn = document.getElementById('cookie-accept');
  var rejectBtn = document.getElementById('cookie-reject');
  var settingsLink = document.getElementById('cookie-settings-link');
  var consent = null;
  try { consent = localStorage.getItem('mwlCookieConsent'); } catch (e) {}

  if (consent === 'accepted') {
    mwlLoadTawk();
  } else if (consent !== 'rejected' && banner) {
    banner.hidden = false;
  }

  if (acceptBtn) acceptBtn.addEventListener('click', function(){
    try { localStorage.setItem('mwlCookieConsent', 'accepted'); } catch (e) {}
    if (banner) banner.hidden = true;
    mwlLoadTawk();
  });
  if (rejectBtn) rejectBtn.addEventListener('click', function(){
    try { localStorage.setItem('mwlCookieConsent', 'rejected'); } catch (e) {}
    if (banner) banner.hidden = true;
  });
  if (settingsLink) settingsLink.addEventListener('click', function(e){
    e.preventDefault();
    if (banner) banner.hidden = false;
  });
})();
</script>
<!--End of cookie consent banner-->

<script>
(function(){
  var yEl = document.getElementById('year');
  if (yEl) { yEl.textContent = new Date().getFullYear(); }

  var KB = [
    { topic: "Our Arrangements", keys: ["arrangement","product","make","wreath","hat box","grave pot","balloon","rose bear","portfolio"],
      a: "We make wreaths, hat box arrangements, grave pots, bobo balloons and hand-made rose bears — all with high-quality artificial flowers that keep their beauty all year round. See our Work & Price List page for the full range, with photos and prices." },
    { topic: "Ordering", keys: ["order","buy","price","cost","how do i"],
      a: "Check out our Work & Price List page for photos and current prices, then get in touch with what you're after — style, colours and any special dates — and we'll come back with options." },
    { topic: "Delivery & Collection", keys: ["deliver","collect","postage","ship"],
      a: "Local delivery and collection can be arranged — just ask when you get in touch." },
    { topic: "Custom Colours", keys: ["colour","color","custom","match"],
      a: "Yes! Most arrangements can be made in your choice of colours to match an event, home or memorial." },
    { topic: "Care", keys: ["last","water","care","wilt","maintain"],
      a: "Our artificial arrangements are made to last — no watering needed, and they'll keep their colour and shape for years." },
  ];
  var FALLBACK = "I don't have a set answer for that yet — tap \\u201cTalk to a real person\\u201d below and we'll get back to you directly.";

  var launcher = document.getElementById('mwl-chat-launcher');
  var panel = document.getElementById('mwl-chat-panel');
  var body = document.getElementById('mwl-chat-body');
  var input = document.getElementById('mwl-chat-input');
  var sendBtn = document.getElementById('mwl-chat-send');
  var badge = document.getElementById('mwl-chat-badge');
  var liveBtn = document.getElementById('mwl-live-chat-btn');
  var opened = false;

  function addMsg(text, sender){
    var div = document.createElement('div');
    div.className = 'chat-msg ' + sender;
    div.textContent = text;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
  }

  function showQuickReplies(){
    var wrap = document.createElement('div');
    wrap.className = 'chat-quick';
    KB.forEach(function(item){
      var btn = document.createElement('button');
      btn.textContent = item.topic;
      btn.addEventListener('click', function(){ handleTopic(item); });
      wrap.appendChild(btn);
    });
    body.appendChild(wrap);
    body.scrollTop = body.scrollHeight;
  }

  function handleTopic(item){
    addMsg(item.topic, 'user');
    setTimeout(function(){ addMsg(item.a, 'bot'); showQuickReplies(); }, 250);
  }

  function handleFreeText(text){
    var lower = text.toLowerCase();
    var match = null;
    for (var i=0;i<KB.length;i++){
      for (var j=0;j<KB[i].keys.length;j++){
        if (lower.indexOf(KB[i].keys[j]) !== -1){ match = KB[i]; break; }
      }
      if (match) break;
    }
    setTimeout(function(){ addMsg(match ? match.a : FALLBACK, 'bot'); showQuickReplies(); }, 250);
  }

  function toggle(){
    opened = !opened;
    panel.classList.toggle('open', opened);
    launcher.classList.toggle('open', opened);
    if (opened) {
      badge.style.display = 'none';
      if (!body.dataset.greeted) {
        addMsg("Hi! I'm the Made With Love assistant. Ask me a quick question, or tap \\u201cTalk to a real person\\u201d to message us directly.", 'bot');
        showQuickReplies();
        body.dataset.greeted = '1';
      }
    }
  }

  launcher.addEventListener('click', toggle);

  sendBtn.addEventListener('click', function(){
    var val = input.value.trim();
    if (!val) return;
    addMsg(val, 'user');
    input.value = '';
    handleFreeText(val);
  });
  input.addEventListener('keydown', function(e){ if (e.key === 'Enter') sendBtn.click(); });

  liveBtn.addEventListener('click', function(){
    if (window.Tawk_API && typeof window.Tawk_API.toggle === 'function') {
      window.Tawk_API.toggle();
    } else {
      window.location.href = 'contact.html';
    }
  });
})();
</script>
"""

def page(title, description, active, body_content, page_hero=None):
    hero_block = ""
    if page_hero:
        hero_block = f"""
<section class="page-hero">
  <div class="wrap">
    <span class="eyebrow">{page_hero['eyebrow']}</span>
    <h1>{page_hero['title']}</h1>
    <p>{page_hero['sub']}</p>
  </div>
</section>
"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Dancing+Script:wght@600;700&family=Playfair+Display:wght@600;700&family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
{nav_html(active)}
{hero_block}
{body_content}
{FOOTER}
{COOKIE_BANNER}
{CHAT_WIDGET}
</body>
</html>
"""

# ---------------- HOME ----------------

HOME_HERO = f"""
<section class="hero" id="top">
  <div class="hero-inner">
    <div>
      <span class="eyebrow">Handmade Artificial Flower Arrangements</span>
      <h1 class="script-title script">Made With Love</h1>
      <p class="lead">Wreaths, hat box arrangements, grave pots, bobo balloons and hand-made rose bears &mdash; each one handmade with care, using beautiful artificial flowers that keep their looks all year round.</p>
      <div class="hero-ctas">
        <a href="pricelist.html" class="btn btn-primary">Our Work &amp; Price List</a>
        <a href="contact.html" class="btn btn-secondary">Get in Touch</a>
      </div>
    </div>
    <div class="hero-photo-card">
      {photo_img("hero", "Made With Love — handmade rose arrangement with heart balloon")}
      <div class="tag-badge hero-badge"><span class="script">Made<br>With<br>Love</span></div>
    </div>
  </div>
</section>
"""

HOME_ABOUT_TEASER = """
<section class="about" id="about-teaser">
  <div class="wrap">
    <span class="eyebrow">Our Story</span>
    <h2>Handmade, with love &mdash; and built to last</h2>
    <p>Every piece is handmade to order, arranged one bloom at a time with the same care you'd put into a bouquet of fresh flowers &mdash; without the watering, wilting or waiting.</p>
    <a href="about.html" class="btn btn-secondary" style="margin-top:10px;">Read Our Story</a>
  </div>
</section>
"""

HOME_FEATURED = f"""
<section class="arrangements" id="featured">
  <div class="wrap">
    <div class="section-head">
      <span class="eyebrow">What We Make</span>
      <h2>A Few Favourites</h2>
      <p>Every piece handmade to order &mdash; see the full range, with prices, in Our Work &amp; Price List.</p>
    </div>
    <div class="prod-grid">
      <div class="prod-card">
        {photo_img("rosebear", "Made With Love — hat box rose arrangement", "&#127913;")}
        <div class="prod-body">
          <h3>Hat Boxes</h3>
          <p>Beautifully arranged artificial blooms in a decorative hat box &mdash; a stunning gift or table centrepiece.</p>
        </div>
      </div>
      <div class="prod-card">
        {photo_img("hatbox", "Made With Love — handbag bouquet arrangement", "&#128092;")}
        <div class="prod-body">
          <h3>Handbag Bouquets</h3>
          <p>A beautifully arranged bouquet presented in a decorative handbag-style box &mdash; a stylish gift with a lasting twist.</p>
        </div>
      </div>
    </div>
    <div style="text-align:center;margin-top:38px;display:flex;gap:14px;justify-content:center;flex-wrap:wrap;">
      <a href="pricelist.html" class="btn btn-primary">See Our Work &amp; Price List</a>
    </div>
  </div>
</section>
"""

WHY = """
<section class="why" id="why">
  <div class="wrap">
    <div class="section-head">
      <span class="eyebrow">Why Made With Love</span>
      <h2>Made to keep its beauty</h2>
      <p>Handmade touches that make the difference.</p>
    </div>
    <div class="why-grid">
      <div class="why-item"><div class="wi-icon">&#129505;</div><h4>Handmade with care</h4><p>Every arrangement made by hand, one bloom at a time.</p></div>
      <div class="why-item"><div class="wi-icon">&#127807;</div><h4>Never wilts</h4><p>No watering needed &mdash; keeps its colour and shape for years.</p></div>
      <div class="why-item"><div class="wi-icon">&#127873;</div><h4>Perfect for any occasion</h4><p>Gifts, celebrations, memorials and everyday touches of colour.</p></div>
      <div class="why-item"><div class="wi-icon">&#127912;</div><h4>Custom colours</h4><p>Most arrangements can be made to match your colours.</p></div>
    </div>
  </div>
</section>
"""

HOME_CTA = """
<section class="contact" id="cta">
  <div class="wrap" style="text-align:center;">
    <span class="eyebrow" style="background:rgba(255,255,255,.15);color:#fffaf3;">Get in touch</span>
    <h2 style="margin-bottom:16px;">Let's talk about your arrangement</h2>
    <p style="color:#ecdcc4;max-width:520px;margin:0 auto 26px;">Tell us what you have in mind &mdash; style, colours, and any special dates.</p>
    <a href="contact.html" class="btn btn-primary">Contact Us</a>
  </div>
</section>
"""

# Loaded once and shared by the Portfolio gallery and the Price List below,
# so every catalogue photo only gets decoded/saved to images/catalogue/ once.
_catalogue_items = load_catalogue_items()
_cleanup_stale_catalogue_photos(os.path.join(BASE, "images", "catalogue"), _catalogue_items)

# Loaded once and shared by the Home page teaser and the News page below.
_blog_posts = load_blog_posts()
_cleanup_stale_blog_photos(os.path.join(BASE, "images", "blog"), _blog_posts)

home_body = HOME_HERO + HOME_ABOUT_TEASER + HOME_FEATURED + blog_teaser_section(_blog_posts) + WHY + HOME_CTA

# ---------------- PORTFOLIO ----------------

# (The Portfolio page was merged into the Price List page - see
# portfolio.html redirect near the bottom. gallery_section() and
# GALLERY_ITEMS are kept in this file but no longer used for a page.)

# ---------------- PRICE LIST ----------------

pricelist_body = pricelist_section(_catalogue_items) + HOME_CTA

# ---------------- ABOUT ----------------

about_body = """
<section class="about" id="about">
  <div class="wrap">
    <h2>Handmade, with love &mdash; and built to last</h2>
    <p>Every piece is handmade to order, arranged one bloom at a time with the same care you'd put into a bouquet of fresh flowers &mdash; without the watering, wilting or waiting.</p>
    <p>From wreaths for the front door to gentle tributes for graveside memorials, each arrangement is made to keep its colour and shape for years, so the love you put into choosing it lasts too.</p>
    <p>Every arrangement starts the same way &mdash; picking out blooms in colours and textures that work together, then building each piece by hand until it feels right. No two are ever quite the same.</p>
  </div>
</section>
""" + WHY + HOME_CTA

# ---------------- CONTACT ----------------

contact_body = """
<section class="contact" id="contact">
  <div class="wrap">
    <div class="section-head">
      <span class="eyebrow" style="background:rgba(255,255,255,.15);color:#fffaf3;">Get in touch</span>
      <h2>Let's talk about your arrangement</h2>
      <p>Tell us what you have in mind &mdash; style, colours, and any special dates &mdash; or message us directly using the chat button in the corner.</p>
    </div>
    <div class="contact-rows">
      <div class="contact-row">
        <div class="icon">&#9993;&#65039;</div>
        <div>
          <div class="label">Email</div>
          <div class="val"><a href="mailto:info@mwlflorals.co.uk">info@mwlflorals.co.uk</a></div>
        </div>
      </div>
    </div>
    <form class="contact-form" id="mwl-contact-form">
      <input type="hidden" name="access_key" value="5f546492-e8a0-47b9-ba5b-e9a3423e9e7b">
      <input type="hidden" name="subject" value="New enquiry from the Made With Love website">
      <input type="hidden" name="from_name" value="Made With Love Website">
      <input type="checkbox" name="botcheck" class="mwl-honeypot" tabindex="-1" autocomplete="off">
      <label for="mf-name">Your Name</label>
      <input type="text" id="mf-name" name="name" required>
      <label for="mf-email">Email</label>
      <input type="email" id="mf-email" name="email" required>
      <label for="mf-message">What are you after?</label>
      <textarea id="mf-message" name="message" placeholder="Tell us the occasion, colours, and any dates that matter..."></textarea>
      <button type="submit" class="btn btn-primary" id="mf-submit">Send Enquiry</button>
      <div class="form-status" id="mf-status" role="status" aria-live="polite"></div>
    </form>
  </div>
</section>
<script>
(function(){
  var form = document.getElementById('mwl-contact-form');
  if(!form) return;
  var status = document.getElementById('mf-status');
  var btn = document.getElementById('mf-submit');
  form.addEventListener('submit', function(e){
    e.preventDefault();
    btn.disabled = true;
    btn.textContent = 'Sending...';
    status.className = 'form-status';
    status.textContent = '';
    var formData = new FormData(form);
    var payload = Object.fromEntries(formData.entries());
    fetch('https://api.web3forms.com/submit', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
      body: JSON.stringify(payload)
    }).then(function(res){ return res.json(); }).then(function(data){
      if (data.success) {
        status.className = 'form-status success';
        status.textContent = "Thanks \\u2014 your message is on its way. We'll be in touch soon.";
        form.reset();
      } else {
        status.className = 'form-status error';
        status.textContent = 'Something went wrong sending that. Please try again, or message us via the chat button.';
      }
      btn.disabled = false;
      btn.textContent = 'Send Enquiry';
    }).catch(function(){
      status.className = 'form-status error';
      status.textContent = 'Something went wrong sending that. Please try again, or message us via the chat button.';
      btn.disabled = false;
      btn.textContent = 'Send Enquiry';
    });
  });
})();
</script>
"""

PRIVACY_BODY = """
<section class="about">
  <div class="wrap" style="max-width:760px;">
    <p style="color:var(--ink-soft);font-size:.92rem;">Last updated: 3 October 2026</p>

    <h2>Who we are</h2>
    <p>Made With Love is a handmade artificial flower arrangement business. You can reach us at <a href="mailto:info@mwlflorals.co.uk">info@mwlflorals.co.uk</a> or via the contact form or chat button on this site. We're the data controller for the personal information described in this policy.</p>

    <h2>What we collect, and why</h2>
    <p><strong>Contact form.</strong> When you use the form on our Contact page, we collect your name, email address and message so we can reply to your enquiry.</p>
    <p><strong>Live chat.</strong> If you message us through the "Talk to a real person" option in the chat widget, your conversation is handled by Tawk.to, our live chat provider, so we can reply to you. Tawk.to may also collect your IP address, browser type, and the pages you've visited, in order to run the chat service.</p>
    <p>We don't run ads on this site, we don't sell your data, and we don't use analytics or tracking cookies.</p>

    <h2>How your contact form is handled</h2>
    <p>Submitting the contact form sends your details through Web3Forms, a third-party form service, which forwards your message straight to our email inbox. Web3Forms doesn't use your details for anything else.</p>

    <h2>Cookies</h2>
    <p>The only non-essential cookie-setting feature on this site is the live chat widget (Tawk.to). It only loads once you accept cookies via the banner shown on your first visit — if you choose "Reject," the chat widget won't load, and you can still reach us by email or the contact form. You can change your choice at any time using the "Cookie Settings" link in the footer.</p>

    <h2>Where your data goes</h2>
    <p>Tawk.to is based in the United States and is certified under the UK Extension to the EU-U.S. Data Privacy Framework, a recognised safeguard for transferring personal data there. Web3Forms relies on Standard Contractual Clauses to safeguard any data transferred outside the UK and EU.</p>

    <h2>How long we keep it</h2>
    <p>We keep enquiry and chat records only as long as needed to deal with your enquiry, and for a reasonable period afterwards in case you get back in touch, after which we delete them.</p>

    <h2>Your rights</h2>
    <p>Under UK GDPR, you can ask what personal data we hold about you, have it corrected or deleted, and object to how we use it. To exercise any of these, email <a href="mailto:info@mwlflorals.co.uk">info@mwlflorals.co.uk</a>. You can also complain to the Information Commissioner's Office (ICO) at <a href="https://ico.org.uk" target="_blank" rel="noopener">ico.org.uk</a> if you're unhappy with how we've handled your data.</p>

    <h2>Contact</h2>
    <p>Questions about this policy or your data: <a href="mailto:info@mwlflorals.co.uk">info@mwlflorals.co.uk</a>.</p>
  </div>
</section>
"""

pages = {
    "index.html": page(
        "Made With Love — Handmade Artificial Flower Arrangements",
        "Made With Love — handmade artificial flower wreaths, hat box arrangements, grave pots, bobo balloons and rose bears. Beautiful arrangements that last.",
        "index.html", home_body,
    ),
    "pricelist.html": page(
        "Our Work &amp; Price List | Made With Love",
        "See our handmade artificial flower arrangements and their current prices — wreaths, hat boxes, handbag bouquets, grave pots, bobo balloons and rose bears.",
        "pricelist.html", pricelist_body,
        page_hero={"eyebrow":"What We Make","title":"Our Work &amp; Price List","sub":"Every piece handmade to order — get in touch for custom colours, sizes or dates."},
    ),
    "news.html": page(
        "News | Made With Love",
        "The latest news and updates from Made With Love — new arrangements, seasonal ranges and what's happening in the workshop.",
        "news.html", news_body(_blog_posts),
        page_hero={"eyebrow":"What's New","title":"News & Updates","sub":"The latest from Made With Love."},
    ),
    "about.html": page(
        "Our Story | Made With Love",
        "Meet Made With Love — handmade artificial flower arrangements made one bloom at a time, built to keep their beauty for years.",
        "about.html", about_body,
        page_hero={"eyebrow":"Our Story","title":"About Made With Love","sub":"Handmade, with love — and built to last."},
    ),
    "contact.html": page(
        "Contact | Made With Love",
        "Get in touch with Made With Love to talk about your handmade artificial flower arrangement — wreaths, hat boxes, grave pots, bobo balloons and rose bears.",
        "contact.html", contact_body,
        page_hero={"eyebrow":"Contact","title":"Let's Talk","sub":"Message us directly via the form below or the chat button, and we'll get back to you."},
    ),
    "privacy.html": page(
        "Privacy Policy | Made With Love",
        "How Made With Love collects, uses and protects your personal information, including our use of cookies and the live chat widget.",
        "privacy.html", PRIVACY_BODY,
        page_hero={"eyebrow":"Your Privacy","title":"Privacy Policy","sub":"How we collect, use and protect your information."},
    ),
}

# The Portfolio page has been merged into "Our Work & Price List". Keep the
# old address working (bookmarks, Google) by sending visitors to the home page.
pages["portfolio.html"] = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Made With Love</title>
<meta http-equiv="refresh" content="0; url=index.html">
<script>window.location.replace('index.html');</script>
</head>
<body>
<p><a href="index.html">Taking you to the Made With Love home page&hellip;</a></p>
</body>
</html>
"""

for fname, html in pages.items():
    with open(os.path.join(BASE, fname), "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", fname, len(html))

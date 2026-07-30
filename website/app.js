const repository = "frigstah/SimpleCast";
const fallbackTag = "v0.9.0-beta.17";

function all(selector) {
  return Array.from(document.querySelectorAll(selector));
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "";
  }
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / (1024 ** index);
  return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

function versionLabel(tag) {
  const version = tag.replace(/^v/i, "");
  const beta = version.match(/beta[.-]?(\d+)/i);
  return beta ? `Beta ${beta[1]}` : version;
}

function setLinks(selector, href) {
  if (!href) {
    return;
  }
  all(selector).forEach((link) => {
    link.href = href;
  });
}

async function loadRelease() {
  const status = document.querySelector(".release-status");
  try {
    const response = await fetch(
      `https://api.github.com/repos/${repository}/releases?per_page=10`,
      {
        headers: {
          Accept: "application/vnd.github+json",
        },
      },
    );
    if (!response.ok) {
      throw new Error(`GitHub returned ${response.status}`);
    }

    const releases = await response.json();
    const release = releases.find((item) => !item.draft);
    if (!release) {
      throw new Error("No published release was found");
    }

    const installer = release.assets.find((asset) =>
      /^SimpleCast-Setup-.*-x64\.exe$/i.test(asset.name)
    );
    const portable = release.assets.find((asset) =>
      /^SimpleCast-Windows-x64-.*-portable\.zip$/i.test(asset.name)
    );
    const checksums = release.assets.find((asset) =>
      /^SHA256SUMS-.*\.txt$/i.test(asset.name)
    );

    setLinks("[data-installer-link]", installer?.browser_download_url);
    setLinks("[data-portable-link]", portable?.browser_download_url);
    setLinks("[data-checksum-link]", checksums?.browser_download_url);
    setLinks("[data-release-notes-link]", release.html_url);
    setLinks(
      "[data-source-link]",
      `https://github.com/${repository}/archive/refs/tags/${release.tag_name}.zip`,
    );

    const releaseTitle = release.name || release.tag_name.replace(/^v/i, "");
    all("[data-release-name]").forEach((element) => {
      element.textContent = releaseTitle;
    });
    all("[data-version-label]").forEach((element) => {
      element.textContent = `${versionLabel(release.tag_name)} · Installer`;
    });
    all("[data-release-badge]").forEach((element) => {
      element.textContent = release.prerelease ? "Public beta" : "Stable release";
    });

    const published = new Date(release.published_at);
    if (!Number.isNaN(published.valueOf())) {
      const formatted = new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
      }).format(published);
      all("[data-release-date]").forEach((element) => {
        element.textContent = formatted;
      });
    }

    if (installer) {
      all("[data-installer-size]").forEach((element) => {
        element.textContent = formatBytes(installer.size);
      });
    }
    if (portable) {
      all("[data-portable-size]").forEach((element) => {
        element.textContent = formatBytes(portable.size);
      });
    }

    status?.setAttribute(
      "title",
      `${releaseTitle} is available to download`,
    );
  } catch (error) {
    console.warn("Using the built-in release links:", error);
    status?.classList.add("is-fallback");
    status?.setAttribute(
      "title",
      `${versionLabel(fallbackTag)} links shown; live release information is temporarily unavailable`,
    );
  }
}

function enableReveals() {
  const elements = all(".reveal");
  if (
    !("IntersectionObserver" in window)
    || window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    elements.forEach((element) => element.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    {
      rootMargin: "0px 0px -8% 0px",
      threshold: 0.08,
    },
  );
  elements.forEach((element) => observer.observe(element));
}

document.querySelector("[data-year]").textContent = new Date().getFullYear();
enableReveals();
loadRelease();

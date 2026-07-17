const PROBES = [375, 583, 585, 750, 850, 875, 916, 999];
const HIDDEN_PROBES = [900];

// Source: Zoloto.xlsx, 2026-07-17.
// Tillachi Bolla uses the exact same public price ranges as Diamant.
const BRAND_FIXED_MAX_PRICES = {
  skupka: {
    583: 1200000,
    585: 1000000,
    850: 1320000,
    875: 1375000,
    900: 1500000,
    916: 1420000,
    999: 1600000,
  },
  diamant: {
    583: 1210000,
    585: 1000000,
    850: 1325000,
    875: 1380000,
    900: 1500000,
    916: 1425000,
    999: 1615000,
  },
  tillachi: {
    583: 1210000,
    585: 1000000,
    850: 1325000,
    875: 1380000,
    900: 1500000,
    916: 1425000,
    999: 1615000,
  },
  goldexpert: {
    583: 1220000,
    585: 1000000,
    850: 1330000,
    875: 1385000,
    900: 1500000,
    916: 1450000,
    999: 1590000,
  },
};

const ROUNDUP_MAX_ADDITIONS = {
  skupka: { 375: 70000 },
  diamant: { 375: 70000 },
  tillachi: { 375: 70000 },
  goldexpert: { 375: 70000 },
};

function excelRound(value, digits = 0) {
  const factor = 10 ** digits;
  return Math.sign(value) * Math.round(Math.abs(value) * factor) / factor;
}

function excelCeiling(value, significance) {
  return Math.ceil(value / significance) * significance;
}

function roundupTo10000(value) {
  return excelCeiling(value, 10000);
}

function roundedBasePrice(probe, mainRate) {
  return excelCeiling((probe / 583 / 10) * mainRate, 0.5) * 10000;
}

function minPrice(probe, mainRate) {
  if (probe === 585) {
    return Math.round(mainRate * 1000);
  }
  return roundedBasePrice(probe, mainRate);
}

function maxPrice(probe, startPrice, brand) {
  if (probe === 750) {
    return 1500000 - startPrice < 200000 ? startPrice + 200000 : 1500000;
  }
  const fixedPrices = BRAND_FIXED_MAX_PRICES[brand] || BRAND_FIXED_MAX_PRICES.diamant;
  if (Object.prototype.hasOwnProperty.call(fixedPrices, probe)) {
    return fixedPrices[probe];
  }
  const additions = ROUNDUP_MAX_ADDITIONS[brand] || ROUNDUP_MAX_ADDITIONS.diamant;
  const addition = additions[probe] || ROUNDUP_MAX_ADDITIONS.diamant[probe] || 0;
  return roundupTo10000(startPrice) + addition;
}

function calculatePrices(mainRate, brand = "diamant", includeHidden = false) {
  const rate = Number(mainRate);
  if (!Number.isFinite(rate) || rate <= 0) {
    throw new Error("mainRate must be a positive number");
  }

  const result = {};
  const probes = includeHidden ? [...PROBES, ...HIDDEN_PROBES] : PROBES;
  const normalizedBrand = String(brand || "diamant").toLowerCase();
  for (const probe of probes) {
    const start = minPrice(probe, rate);
    result[String(probe)] = [start, maxPrice(probe, start, normalizedBrand)];
  }
  return result;
}

function generatePriceRange(mainRate, brand = "diamant") {
  return calculatePrices(mainRate, brand);
}

function formatPrice(value) {
  return Math.round(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

module.exports = {
  calculatePrices,
  generatePriceRange,
  formatPrice,
};

if (require.main === module) {
  const mainRate = Number(process.argv[2] || 1200);
  console.log(JSON.stringify(generatePriceRange(mainRate), null, 2));
}

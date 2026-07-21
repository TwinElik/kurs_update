const PROBES = [375, 583, 585, 750, 850, 875, 916, 999];
const HIDDEN_PROBES = [900];

// Source: Zoloto.xlsx, main rate 870.
// Keep the workbook's "to minus from" spread per brand/probe instead of
// freezing a "to" value that becomes invalid when the main rate changes.
// Tillachi Bolla uses the same public ranges as Diamant.
const BRAND_MAX_ADDITIONS = {
  skupka: {
    375: 70000,
    583: 330000,
    585: 180000,
    750: 380000,
    850: 75000,
    875: 75000,
    900: 155000,
    916: 90000,
    999: 105000,
  },
  diamant: {
    375: 70000,
    583: 340000,
    585: 180000,
    750: 380000,
    850: 75000,
    875: 85000,
    900: 155000,
    916: 60000,
    999: 120000,
  },
  tillachi: {
    375: 70000,
    583: 340000,
    585: 180000,
    750: 380000,
    850: 75000,
    875: 85000,
    900: 155000,
    916: 60000,
    999: 120000,
  },
  goldexpert: {
    375: 70000,
    583: 350000,
    585: 180000,
    750: 380000,
    850: 70000,
    875: 90000,
    900: 155000,
    916: 80000,
    999: 95000,
  },
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
  const additions = BRAND_MAX_ADDITIONS[brand] || BRAND_MAX_ADDITIONS.diamant;
  const addition = additions[probe] || BRAND_MAX_ADDITIONS.diamant[probe] || 0;
  return startPrice + addition;
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

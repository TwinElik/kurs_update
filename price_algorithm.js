const PROBES = [375, 583, 585, 750, 850, 875, 916, 999];
const HIDDEN_PROBES = [900];

const BRAND_ADDITIONS = {
  tillachi: {
    375: 40000,
    585: 190000,
    850: 190000,
    875: 190000,
    900: 190000,
    916: 190000,
    999: 140000,
  },
  diamant: {
    375: 50000,
    585: 200000,
    850: 200000,
    875: 200000,
    900: 200000,
    916: 200000,
    999: 150000,
  },
  skupka: {
    375: 60000,
    585: 210000,
    850: 210000,
    875: 210000,
    900: 210000,
    916: 210000,
    999: 160000,
  },
  goldexpert: {
    375: 70000,
    585: 220000,
    850: 220000,
    875: 220000,
    900: 220000,
    916: 220000,
    999: 170000,
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
  if (probe === 583 || probe === 750) {
    return 1500000 - startPrice < 200000 ? startPrice + 200000 : 1500000;
  }
  const additions = BRAND_ADDITIONS[brand] || BRAND_ADDITIONS.diamant;
  const addition = additions[probe] || BRAND_ADDITIONS.diamant[probe] || 200000;
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

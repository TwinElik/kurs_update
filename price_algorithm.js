const PROBES = [583, 585, 750, 850, 875, 916, 999];

function excelRound(value, digits = 0) {
  const factor = 10 ** digits;
  return Math.sign(value) * Math.round(Math.abs(value) * factor) / factor;
}

function excelCeiling(value, significance) {
  return Math.ceil(value / significance) * significance;
}

function roundedBasePrice(probe, mainRate) {
  return excelCeiling((probe / 583 / 10) * mainRate, 0.5) * 10000;
}

function minPrice(probe, mainRate) {
  if (probe === 585) {
    return Math.round(excelRound(585 / 583, 5) * mainRate * 1000);
  }
  return roundedBasePrice(probe, mainRate);
}

function maxPrice(probe, startPrice) {
  if (probe === 583 || probe === 750) {
    return 1500000 - startPrice < 200000 ? startPrice + 200000 : 1500000;
  }
  if (probe === 999) {
    return startPrice + 150000;
  }
  return startPrice + 200000;
}

function generatePriceRange(mainRate) {
  const rate = Number(mainRate);
  if (!Number.isFinite(rate) || rate <= 0) {
    throw new Error("mainRate must be a positive number");
  }

  const result = {};
  for (const probe of PROBES) {
    const start = minPrice(probe, rate);
    result[String(probe)] = [start, maxPrice(probe, start)];
  }
  return result;
}

function formatPrice(value) {
  return Math.round(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

module.exports = {
  generatePriceRange,
  formatPrice,
};

if (require.main === module) {
  const mainRate = Number(process.argv[2] || 1200);
  console.log(JSON.stringify(generatePriceRange(mainRate), null, 2));
}

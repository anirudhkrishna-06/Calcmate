const STOP_WORDS = new Set([
    'a', 'an', 'and', 'are', 'by', 'find', 'for', 'from', 'how', 'if', 'in', 'is', 'it',
    'of', 'on', 'or', 'show', 'simplify', 'solve', 'that', 'the', 'to', 'what', 'with',
]);

export const TOPIC_CATALOG = [
    {
        id: 'algebra',
        label: 'Algebra',
        keywords: ['equation', 'quadratic', 'polynomial', 'factor', 'variable', 'expression', 'inequality', 'roots'],
        stems: ['algebra', 'simplif', 'expand', 'factor', 'solve for', 'linear equation'],
        patterns: [/\bx\b/, /\by\b/, /\bquadratic\b/, /\bpolynomial\b/, /\b2x\b/, /\b3x\b/],
        weight: 1.16,
    },
    {
        id: 'geometry',
        label: 'Geometry',
        keywords: ['triangle', 'circle', 'angle', 'polygon', 'radius', 'diameter', 'perimeter', 'theorem'],
        stems: ['geometry', 'hypoten', 'congruen', 'similar', 'parallel', 'perpendicular'],
        patterns: [/\btriangle\b/, /\bcircle\b/, /\bangle\b/, /\bpolygon\b/],
        weight: 1.12,
    },
    {
        id: 'coordinate_geometry',
        label: 'Coordinate Geometry',
        keywords: ['slope', 'intercept', 'distance', 'midpoint', 'coordinate', 'graph', 'line', 'parabola'],
        stems: ['coordinate', 'cartesian', 'scatter', 'straight line'],
        patterns: [/\(\s*-?\d+\s*,\s*-?\d+\s*\)/, /\by\s*=\s*mx\b/i, /\bslope\b/],
        weight: 1.1,
    },
    {
        id: 'mensuration',
        label: 'Mensuration',
        keywords: ['volume', 'surface area', 'area', 'cube', 'cuboid', 'cylinder', 'cone', 'sphere'],
        stems: ['mensurat', 'circumfer', 'hemispher', 'prism'],
        patterns: [/\bvolume\b/, /\bsurface area\b/, /\barea of\b/],
        weight: 1.12,
    },
    {
        id: 'trigonometry',
        label: 'Trigonometry',
        keywords: ['sine', 'cosine', 'tangent', 'secant', 'cosecant', 'cotangent', 'identity', 'angle of elevation'],
        stems: ['trig', 'sin', 'cos', 'tan'],
        patterns: [/\bsin\b/, /\bcos\b/, /\btan\b/, /\bcot\b/, /\bsec\b/, /\bcosec\b/],
        weight: 1.18,
    },
    {
        id: 'calculus',
        label: 'Calculus',
        keywords: ['derivative', 'integral', 'limit', 'differentiate', 'integrate', 'rate of change', 'slope of tangent'],
        stems: ['calculus', 'differenti', 'integrat', 'continu', 'gradient'],
        patterns: [/\bd\/dx\b/i, /\b∫\b/, /\blim\b/, /\bderivative\b/],
        weight: 1.22,
    },
    {
        id: 'probability',
        label: 'Probability',
        keywords: ['probability', 'chance', 'event', 'sample space', 'random', 'outcome', 'independent', 'conditional'],
        stems: ['probab', 'likelihood', 'bayes'],
        patterns: [/\bprobability\b/, /\bp\(/i, /\bchance\b/],
        weight: 1.16,
    },
    {
        id: 'statistics',
        label: 'Statistics',
        keywords: ['mean', 'median', 'mode', 'variance', 'standard deviation', 'data', 'histogram', 'distribution'],
        stems: ['statist', 'average', 'quartile', 'percentile'],
        patterns: [/\bmean\b/, /\bmedian\b/, /\bmode\b/, /\bstandard deviation\b/],
        weight: 1.14,
    },
    {
        id: 'number_theory',
        label: 'Number Theory',
        keywords: ['prime', 'factorisation', 'divisor', 'multiple', 'gcd', 'lcm', 'modulo', 'remainder'],
        stems: ['divisib', 'number theor', 'coprime', 'congruen'],
        patterns: [/\bprime\b/, /\bmod\b/, /\bremainder\b/, /\bgcd\b/, /\blcm\b/],
        weight: 1.12,
    },
    {
        id: 'arithmetic',
        label: 'Arithmetic',
        keywords: ['fraction', 'decimal', 'ratio', 'percent', 'percentage', 'sum', 'difference', 'product'],
        stems: ['arithmet', 'multiply', 'divide', 'subtract', 'addition'],
        patterns: [/\b\d+\s*\/\s*\d+\b/, /\bpercent(age)?\b/, /\bratio\b/],
        weight: 1.06,
    },
    {
        id: 'combinatorics',
        label: 'Combinatorics',
        keywords: ['permutation', 'combination', 'arrangement', 'selection', 'counting', 'binomial', 'ways'],
        stems: ['combinator', 'arrange', 'choose'],
        patterns: [/\bncr\b/i, /\bnpr\b/i, /\bcombination\b/, /\bpermutation\b/],
        weight: 1.15,
    },
    {
        id: 'linear_algebra',
        label: 'Linear Algebra',
        keywords: ['matrix', 'vector', 'determinant', 'eigenvalue', 'eigenvector', 'transpose', 'basis', 'dimension'],
        stems: ['linear algebra', 'gaussian elimin', 'row reduc'],
        patterns: [/\bmatrix\b/, /\bvector\b/, /\bdeterminant\b/],
        weight: 1.2,
    },
];

const TOPIC_BY_ID = Object.fromEntries(TOPIC_CATALOG.map((topic) => [topic.id, topic]));

const normalizeInput = (text = '') =>
    text
        .toLowerCase()
        .replace(/[^a-z0-9\s/%^().,+\-*=]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

const tokenize = (normalizedText) =>
    normalizedText
        .split(' ')
        .filter((token) => token && !STOP_WORDS.has(token));

const createNGrams = (tokens, size) => {
    const grams = [];
    for (let index = 0; index <= tokens.length - size; index += 1) {
        grams.push(tokens.slice(index, index + size).join(' '));
    }
    return grams;
};

const scoreTopicAgainstText = (topic, normalizedText, tokens, ngrams) => {
    let score = 0;
    const reasons = [];

    topic.keywords.forEach((keyword) => {
        if (normalizedText.includes(keyword)) {
            score += keyword.includes(' ') ? 4.6 : 3.2;
            reasons.push(keyword);
        }
    });

    topic.stems.forEach((stem) => {
        if (normalizedText.includes(stem)) {
            score += stem.includes(' ') ? 3.4 : 2.4;
            reasons.push(stem);
        }
    });

    topic.patterns.forEach((pattern) => {
        if (pattern.test(normalizedText)) {
            score += 4.2;
            reasons.push(pattern.source);
        }
    });

    tokens.forEach((token) => {
        if (topic.keywords.some((keyword) => keyword === token)) {
            score += 0.9;
        }
    });

    ngrams.forEach((gram) => {
        if (topic.keywords.includes(gram) || topic.stems.includes(gram)) {
            score += 1.4;
        }
    });

    const variableDensity = (normalizedText.match(/\b[a-z]\b/g) || []).length;
    const operatorDensity = (normalizedText.match(/[=+\-*/^]/g) || []).length;

    if (topic.id === 'algebra' && variableDensity >= 2 && operatorDensity >= 1) {
        score += 2.6;
        reasons.push('variable-pattern');
    }

    if (topic.id === 'arithmetic' && /\b\d+\s*[+\-*/]\s*\d+/.test(normalizedText)) {
        score += 2.1;
        reasons.push('numeric-operation');
    }

    if (topic.id === 'statistics' && /\b(table|dataset|survey)\b/.test(normalizedText)) {
        score += 2.1;
        reasons.push('data-context');
    }

    if (topic.id === 'probability' && /\b(card|dice|coin|spinner)\b/.test(normalizedText)) {
        score += 2.3;
        reasons.push('chance-context');
    }

    if (topic.id === 'mensuration' && /\bcm2\b|\bcm3\b|\bm2\b|\bm3\b/.test(normalizedText)) {
        score += 2.0;
        reasons.push('unit-shape-context');
    }

    return {
        score: score * topic.weight,
        reasons,
    };
};

const confidenceFromScores = (bestScore, runnerUpScore) => {
    if (bestScore <= 0) return 0.18;
    const margin = Math.max(bestScore - runnerUpScore, 0);
    return Math.min(0.98, 0.4 + bestScore / 18 + margin / 12);
};

export function classifyMathTopic(text = '') {
    const normalizedText = normalizeInput(text);

    if (!normalizedText) {
        return {
            topicId: 'arithmetic',
            topicTag: 'Arithmetic',
            confidence: 0.18,
            rankedTopics: [],
            reasons: [],
        };
    }

    const tokens = tokenize(normalizedText);
    const ngrams = [
        ...createNGrams(tokens, 2),
        ...createNGrams(tokens, 3),
    ];

    const ranked = TOPIC_CATALOG.map((topic) => {
        const { score, reasons } = scoreTopicAgainstText(topic, normalizedText, tokens, ngrams);
        return {
            topicId: topic.id,
            topicTag: topic.label,
            score: Number(score.toFixed(3)),
            reasons: Array.from(new Set(reasons)).slice(0, 5),
        };
    }).sort((left, right) => right.score - left.score);

    const best = ranked[0];
    const runnerUp = ranked[1] || { score: 0 };

    if (!best || best.score <= 0.5) {
        return {
            topicId: 'arithmetic',
            topicTag: 'Arithmetic',
            confidence: 0.22,
            rankedTopics: ranked.slice(0, 4),
            reasons: ['fallback-general-math'],
        };
    }

    return {
        topicId: best.topicId,
        topicTag: best.topicTag,
        confidence: Number(confidenceFromScores(best.score, runnerUp.score).toFixed(2)),
        rankedTopics: ranked.slice(0, 4),
        reasons: best.reasons,
    };
}

export function getTopicMeta(topicId) {
    return TOPIC_BY_ID[topicId] || null;
}

export const TOPIC_LABELS = TOPIC_CATALOG.map((topic) => topic.label);

import { PrismaClient } from '@prisma/client'
import { readFileSync } from 'fs'
import { join } from 'path'

const prisma = new PrismaClient()
// Keep in sync with IMMUTABLE_CORE in backend/app/persona/profile.py.
const DEFAULT_PERSONALITY = JSON.stringify({
    name: 'AI Friend',
    core_personality: {
        immutable: {
            values: ['Honesty', 'Privacy'],
            base_tone: 'Warm, intellectual, and slightly protective',
            boundaries: ['Will never share user data', 'Will not adopt toxic behavior']
        },
        adaptive_traits: []
    },
    speaking_style: { pace: 'natural', verbosity: 'balanced' },
    conversation_rules: { avoid: [] }
})
const DEFAULT_HISTORY = JSON.stringify({
    relationship: 'Friend',
    memories: []
})

function readSeedOrFallback(path, fallbackValue, label) {
    try {
        return readFileSync(path, 'utf8')
    } catch (err) {
        if (err && err.code === 'ENOENT') {
            console.warn(`Seed file not found for ${label}, using defaults: ${path}`)
            return fallbackValue
        }

        console.error(
            `Failed to read seed file for ${label} at ${path}: ${err && err.message ? err.message : err}`
        )
        throw err
    }
}

async function main() {
    const personalityStr = readSeedOrFallback(
        join(__dirname, '../../backend/app/personality.json'),
        DEFAULT_PERSONALITY,
        'personality'
    )
    const historyStr = readSeedOrFallback(
        join(__dirname, '../../backend/app/history.json'),
        DEFAULT_HISTORY,
        'history'
    )

    console.log('--- Seeding Start ---')

    try {
        const existing = await prisma.agentConfig.findUnique({ where: { id: 1 } })

        // Insert-only, matching ConversationHistoryStore._ensure_config_exists on the
        // Python side: an existing row means a persona -- possibly evolved through
        // reflection -- already lives there, and this seed script must not overwrite it.
        if (existing) {
            console.log('Record exists, leaving it untouched.')
        } else {
            console.log('Record does not exist, creating...')
            await prisma.agentConfig.create({
                data: {
                    id: 1,
                    personality: personalityStr,
                    backgroundHistory: historyStr,
                }
            })
        }
        console.log('Seeding successful.')
    } catch (err) {
        console.error('Operation failed:', err)
        throw err
    }
}

main()
    .catch((e) => {
        process.exit(1)
    })
    .finally(async () => {
        await prisma.$disconnect()
    })

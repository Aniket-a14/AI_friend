import { PrismaClient } from '@prisma/client'
import { readFileSync } from 'fs'
import { join } from 'path'

const prisma = new PrismaClient()
const DEFAULT_PERSONALITY = JSON.stringify({
    name: 'AI Friend',
    core_personality: {
        immutable: {
            values: ['Honesty', 'Privacy', 'Curiosity'],
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
        console.warn(`Seed file not found for ${label}, using defaults: ${path}`)
        return fallbackValue
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

        if (existing) {
            console.log('Record exists, updating...')
            await prisma.agentConfig.update({
                where: { id: 1 },
                data: {
                    personality: personalityStr,
                    backgroundHistory: historyStr,
                }
            })
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

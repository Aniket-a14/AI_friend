import { PrismaClient } from '@prisma/client'
import { readFileSync } from 'fs'
import { join } from 'path'

const prisma = new PrismaClient()

async function main() {
    const personalityStr = readFileSync(join(__dirname, '../../backend/app/personality.json'), 'utf8')
    const historyStr = readFileSync(join(__dirname, '../../backend/app/history.json'), 'utf8')

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

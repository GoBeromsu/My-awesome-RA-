#!/bin/bash
# Setup demo user and project for Overleaf development environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Support both host machine (fixtures/latex) and container (/fixtures/latex) paths
if [ -d "/fixtures/latex" ]; then
    FIXTURES_DIR="/fixtures/latex"
else
    FIXTURES_DIR="$PROJECT_DIR/fixtures/latex"
fi

# Use environment variable or default to overleaf-web (from deployment/docker-compose.yml)
# For development with overleaf/develop, use: CONTAINER_NAME=develop-web-1 ./setup-demo.sh
CONTAINER_NAME="${CONTAINER_NAME:-overleaf-web}"

DEMO_EMAIL="demo@example.com"
DEMO_PASSWORD="Demo@2024!Secure"
PROJECT_NAME="Upstage ambassador demo"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=================================="
echo "  My Awesome RA - Demo Setup"
echo "=================================="
echo

# Wait for web container to be ready
echo -e "${YELLOW}Waiting for Overleaf web container...${NC}"
for i in {1..30}; do
    if docker exec $CONTAINER_NAME echo "ready" >/dev/null 2>&1; then
        echo -e "${GREEN}Container ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}Error: Container not ready after 60 seconds${NC}"
        exit 1
    fi
    sleep 2
done

# Step 1: Create demo user and get user ID
echo
echo -e "${YELLOW}Step 1: Creating demo user...${NC}"

USER_ID=$(docker exec $CONTAINER_NAME sh -c "cd /overleaf/services/web && node --input-type=module -e \"
import { db } from './app/src/infrastructure/mongodb.mjs';
import bcrypt from 'bcrypt';

const DEMO_EMAIL = '$DEMO_EMAIL';
const DEMO_PASSWORD = '$DEMO_PASSWORD';

async function createDemoUser() {
    // Delete existing demo user
    await db.users.deleteMany({ email: DEMO_EMAIL });

    const hashedPassword = await bcrypt.hash(DEMO_PASSWORD, 12);

    const result = await db.users.insertOne({
        email: DEMO_EMAIL,
        hashedPassword: hashedPassword,
        first_name: 'Demo',
        last_name: 'User',
        isAdmin: false,
        emails: [{
            email: DEMO_EMAIL,
            createdAt: new Date(),
            confirmedAt: new Date(),
            reversedHostname: 'moc.elpmaxe'
        }],
        signUpDate: new Date(),
        features: {
            collaborators: -1,
            versioning: true,
            dropbox: true,
            github: true,
            compileTimeout: 180,
            compileGroup: 'standard',
            templates: true,
            references: true
        }
    });

    console.log(result.insertedId.toString());
    process.exit(0);
}

createDemoUser().catch(err => {
    console.error('Error:', err);
    process.exit(1);
});
\"" 2>/dev/null | tail -1)

if [ -z "$USER_ID" ]; then
    echo -e "${RED}Error: Failed to create demo user${NC}"
    exit 1
fi

echo -e "${GREEN}Demo user created with ID: $USER_ID${NC}"

# Step 2: Delete any existing demo projects
echo
echo -e "${YELLOW}Step 2: Cleaning up existing demo projects...${NC}"

docker exec $CONTAINER_NAME sh -c "cd /overleaf/services/web && node --input-type=module -e \"
import { db } from './app/src/infrastructure/mongodb.mjs';
import mongodb from 'mongodb-legacy';
const { ObjectId } = mongodb;

async function cleanupProjects() {
    const userId = new ObjectId('$USER_ID');
    const result = await db.projects.deleteMany({ owner_ref: userId });
    console.log('Deleted ' + result.deletedCount + ' existing projects');
    process.exit(0);
}

cleanupProjects().catch(err => {
    console.error('Error:', err);
    process.exit(1);
});
\"" 2>&1

# Step 3: Create demo project with fixtures
echo
echo -e "${YELLOW}Step 3: Creating demo project...${NC}"

# Copy fixtures to container
echo "Copying LaTeX files to container..."
docker cp "$FIXTURES_DIR/." $CONTAINER_NAME:/tmp/demo-latex/

# Create project and add files
PROJECT_ID=$(docker exec $CONTAINER_NAME sh -c "cd /overleaf/services/web && node --input-type=module -e \"
import fs from 'node:fs';
import path from 'node:path';
import ProjectCreationHandler from './app/src/Features/Project/ProjectCreationHandler.mjs';
import ProjectEntityUpdateHandler from './app/src/Features/Project/ProjectEntityUpdateHandler.mjs';
import mongodb from 'mongodb-legacy';
const { ObjectId } = mongodb;

const userId = '$USER_ID';
const projectName = '$PROJECT_NAME';
const fixturesDir = '/tmp/demo-latex';

async function createDemoProject() {
    // Create blank project
    const project = await ProjectCreationHandler.promises.createBlankProject(
        userId,
        projectName
    );

    const projectId = project._id;
    const rootFolderId = project.rootFolder[0]._id;

    console.error('Project created:', projectId.toString());

    // Read main.tex as root doc
    const mainTexPath = path.join(fixturesDir, 'main.tex');
    if (fs.existsSync(mainTexPath)) {
        const mainTexContent = fs.readFileSync(mainTexPath, 'utf-8');
        const lines = mainTexContent.split('\\n');

        const { doc } = await ProjectEntityUpdateHandler.promises.addDoc(
            projectId,
            rootFolderId,
            'main.tex',
            lines,
            userId,
            'demo-setup'
        );

        await ProjectEntityUpdateHandler.promises.setRootDoc(projectId, doc._id);
        console.error('Added main.tex as root doc');
    }

    // Add other .tex files
    const texFiles = fs.readdirSync(fixturesDir).filter(f =>
        f.endsWith('.tex') && f !== 'main.tex'
    );

    for (const texFile of texFiles) {
        const filePath = path.join(fixturesDir, texFile);
        const content = fs.readFileSync(filePath, 'utf-8');
        const lines = content.split('\\n');

        await ProjectEntityUpdateHandler.promises.addDoc(
            projectId,
            rootFolderId,
            texFile,
            lines,
            userId,
            'demo-setup'
        );
        console.error('Added:', texFile);
    }

    // Add .bbl file
    const bblFiles = fs.readdirSync(fixturesDir).filter(f => f.endsWith('.bbl'));
    for (const bblFile of bblFiles) {
        const filePath = path.join(fixturesDir, bblFile);
        const content = fs.readFileSync(filePath, 'utf-8');
        const lines = content.split('\\n');

        await ProjectEntityUpdateHandler.promises.addDoc(
            projectId,
            rootFolderId,
            bblFile,
            lines,
            userId,
            'demo-setup'
        );
        console.error('Added:', bblFile);
    }

    // Add .bib file
    const bibFiles = fs.readdirSync(fixturesDir).filter(f => f.endsWith('.bib'));
    for (const bibFile of bibFiles) {
        const filePath = path.join(fixturesDir, bibFile);
        const content = fs.readFileSync(filePath, 'utf-8');
        const lines = content.split('\\n');

        await ProjectEntityUpdateHandler.promises.addDoc(
            projectId,
            rootFolderId,
            bibFile,
            lines,
            userId,
            'demo-setup'
        );
        console.error('Added:', bibFile);
    }

    // Add .cls, .clo, and .bst files
    const clsFiles = fs.readdirSync(fixturesDir).filter(f =>
        f.endsWith('.cls') || f.endsWith('.clo') || f.endsWith('.bst')
    );
    for (const clsFile of clsFiles) {
        const filePath = path.join(fixturesDir, clsFile);
        const content = fs.readFileSync(filePath, 'utf-8');
        const lines = content.split('\\n');

        await ProjectEntityUpdateHandler.promises.addDoc(
            projectId,
            rootFolderId,
            clsFile,
            lines,
            userId,
            'demo-setup'
        );
        console.error('Added:', clsFile);
    }

    // Add image files (with error handling - history service may not be configured)
    const imageFiles = fs.readdirSync(fixturesDir).filter(f =>
        f.endsWith('.png') || f.endsWith('.jpg') || f.endsWith('.jpeg') || f.endsWith('.pdf')
    );

    for (const imageFile of imageFiles) {
        const filePath = path.join(fixturesDir, imageFile);
        try {
            await ProjectEntityUpdateHandler.promises.addFile(
                projectId,
                rootFolderId,
                imageFile,
                filePath,
                null,
                userId,
                'demo-setup'
            );
            console.error('Added image:', imageFile);
        } catch (err) {
            console.error('Warning: Could not add image (history service may not be configured):', imageFile);
        }
    }

    // Output project ID to stdout
    console.log(projectId.toString());
    process.exit(0);
}

createDemoProject().catch(err => {
    console.error('Error creating project:', err);
    process.exit(1);
});
\"" 2>&1 | tee /dev/stderr | tail -1)

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "undefined" ]; then
    echo -e "${RED}Error: Failed to create demo project${NC}"
    docker exec $CONTAINER_NAME rm -rf /tmp/demo-latex 2>/dev/null || true
    exit 1
fi

# Step 4: Upload images via HTTP API
echo
echo -e "${YELLOW}Step 4: Uploading images via HTTP API...${NC}"

# Get root folder ID
ROOT_FOLDER_ID=$(docker exec $CONTAINER_NAME sh -c "cd /overleaf/services/web && node --input-type=module -e \"
import { db } from './app/src/infrastructure/mongodb.mjs';
import mongodb from 'mongodb-legacy';
const { ObjectId } = mongodb;

const project = await db.projects.findOne({ _id: new ObjectId('$PROJECT_ID') });
console.log(project.rootFolder[0]._id.toString());
process.exit(0);
\"" 2>/dev/null)

# Upload images via HTTP API inside container
docker exec $CONTAINER_NAME sh -c "
COOKIE_FILE='/tmp/overleaf-cookie'

# Login to get session
curl -s -c \$COOKIE_FILE -b \$COOKIE_FILE \\
    -X POST http://localhost:3000/login \\
    -H 'Content-Type: application/json' \\
    -d '{\"email\":\"$DEMO_EMAIL\",\"password\":\"$DEMO_PASSWORD\"}' >/dev/null

# Upload each image
for IMG in /tmp/demo-latex/*.png /tmp/demo-latex/*.jpg /tmp/demo-latex/*.jpeg 2>/dev/null; do
    if [ -f \"\$IMG\" ]; then
        IMG_NAME=\$(basename \"\$IMG\")
        RESULT=\$(curl -s -b \$COOKIE_FILE \\
            -X POST \"http://localhost:3000/project/$PROJECT_ID/upload?folder_id=$ROOT_FOLDER_ID\" \\
            -F \"name=\$IMG_NAME\" \\
            -F \"qqfile=@\$IMG;filename=\$IMG_NAME\" 2>&1)
        if echo \"\$RESULT\" | grep -q 'entity_id'; then
            echo \"  Uploaded: \$IMG_NAME\"
        else
            echo \"  Warning: Could not upload \$IMG_NAME\"
        fi
    fi
done

rm -f \$COOKIE_FILE
"

# Cleanup temp files
docker exec $CONTAINER_NAME rm -rf /tmp/demo-latex 2>/dev/null || true

echo
echo -e "${GREEN}=================================="
echo "  Demo Setup Complete!"
echo "==================================${NC}"
echo
echo "Login credentials:"
echo "  Email:    $DEMO_EMAIL"
echo "  Password: $DEMO_PASSWORD"
echo
echo "Demo project: $PROJECT_NAME"
echo "Project ID:   $PROJECT_ID"
echo
echo -e "Access Overleaf at: ${GREEN}http://localhost${NC}"
echo

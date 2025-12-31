import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Politician, getPartyColor } from "@/lib/api";

interface PoliticianCardProps {
    politician: Politician;
}

export function PoliticianCard({ politician }: PoliticianCardProps) {
    return (
        <Link href={`/politicians/${politician.id}`}>
            <Card className="group hover:shadow-lg transition-shadow cursor-pointer h-full">
                <CardContent className="p-6">
                    {/* Avatar */}
                    <div className="flex justify-center mb-4">
                        <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center text-3xl">
                            {politician.imageUrl ? (
                                <img
                                    src={politician.imageUrl}
                                    alt={politician.name}
                                    className="w-full h-full rounded-full object-cover"
                                />
                            ) : (
                                "👤"
                            )}
                        </div>
                    </div>

                    {/* Name */}
                    <h3 className="font-semibold text-lg text-center group-hover:text-primary transition-colors line-clamp-1">
                        {politician.name}
                    </h3>

                    {/* Party Badge */}
                    <div className="flex justify-center mt-2">
                        <Badge
                            style={{ backgroundColor: getPartyColor(politician.party) }}
                            className="text-white"
                        >
                            {politician.party}
                        </Badge>
                    </div>

                    {/* Position */}
                    <p className="text-sm text-muted-foreground text-center mt-3 line-clamp-1">
                        {politician.position}
                    </p>
                    <p className="text-sm text-muted-foreground text-center line-clamp-1">
                        {politician.state}
                    </p>

                    {/* Promise Score (if available) */}
                    {politician.promiseScore !== undefined && (
                        <div className="mt-4">
                            <div className="text-xs text-muted-foreground text-center mb-1">
                                Promise Score
                            </div>
                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-primary transition-all"
                                    style={{ width: `${politician.promiseScore}%` }}
                                />
                            </div>
                            <div className="text-xs text-center mt-1 text-primary font-medium">
                                {politician.promiseScore}%
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>
        </Link>
    );
}

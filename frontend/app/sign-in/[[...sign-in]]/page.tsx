import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="grid min-h-svh place-items-center px-6">
      <SignIn />
    </div>
  );
}
